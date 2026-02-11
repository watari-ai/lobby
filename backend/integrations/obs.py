"""
OBS WebSocket統合モジュール

OBS Studio 28+（obs-websocket 5.x）との連携機能。
- シーン切り替え
- ソース制御（表示/非表示、トランスフォーム）
- 仮想カメラ出力
- 録画制御
- ストリーミング制御
"""

import asyncio
import base64
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import websockets
from loguru import logger
from websockets.exceptions import ConnectionClosed


class OBSEventType(str, Enum):
    """OBS WebSocketイベントタイプ"""
    # General
    EXIT_STARTED = "ExitStarted"
    VENDOR_EVENT = "VendorEvent"
    
    # Config
    CURRENT_SCENE_COLLECTION_CHANGING = "CurrentSceneCollectionChanging"
    CURRENT_SCENE_COLLECTION_CHANGED = "CurrentSceneCollectionChanged"
    CURRENT_PROFILE_CHANGING = "CurrentProfileChanging"
    CURRENT_PROFILE_CHANGED = "CurrentProfileChanged"
    
    # Scenes
    SCENE_CREATED = "SceneCreated"
    SCENE_REMOVED = "SceneRemoved"
    SCENE_NAME_CHANGED = "SceneNameChanged"
    CURRENT_PROGRAM_SCENE_CHANGED = "CurrentProgramSceneChanged"
    CURRENT_PREVIEW_SCENE_CHANGED = "CurrentPreviewSceneChanged"
    SCENE_LIST_CHANGED = "SceneListChanged"
    
    # Inputs
    INPUT_CREATED = "InputCreated"
    INPUT_REMOVED = "InputRemoved"
    INPUT_NAME_CHANGED = "InputNameChanged"
    INPUT_SETTINGS_CHANGED = "InputSettingsChanged"
    INPUT_ACTIVE_STATE_CHANGED = "InputActiveStateChanged"
    INPUT_SHOW_STATE_CHANGED = "InputShowStateChanged"
    INPUT_MUTE_STATE_CHANGED = "InputMuteStateChanged"
    INPUT_VOLUME_CHANGED = "InputVolumeChanged"
    INPUT_AUDIO_BALANCE_CHANGED = "InputAudioBalanceChanged"
    INPUT_AUDIO_SYNC_OFFSET_CHANGED = "InputAudioSyncOffsetChanged"
    INPUT_AUDIO_TRACKS_CHANGED = "InputAudioTracksChanged"
    INPUT_AUDIO_MONITOR_TYPE_CHANGED = "InputAudioMonitorTypeChanged"
    
    # Outputs
    STREAM_STATE_CHANGED = "StreamStateChanged"
    RECORD_STATE_CHANGED = "RecordStateChanged"
    REPLAY_BUFFER_STATE_CHANGED = "ReplayBufferStateChanged"
    VIRTUAL_CAM_STATE_CHANGED = "VirtualcamStateChanged"
    REPLAY_BUFFER_SAVED = "ReplayBufferSaved"
    
    # Scene Items
    SCENE_ITEM_CREATED = "SceneItemCreated"
    SCENE_ITEM_REMOVED = "SceneItemRemoved"
    SCENE_ITEM_LIST_REINDEXED = "SceneItemListReindexed"
    SCENE_ITEM_ENABLE_STATE_CHANGED = "SceneItemEnableStateChanged"
    SCENE_ITEM_LOCK_STATE_CHANGED = "SceneItemLockStateChanged"
    SCENE_ITEM_SELECTED = "SceneItemSelected"
    SCENE_ITEM_TRANSFORM_CHANGED = "SceneItemTransformChanged"
    
    # Media Inputs
    MEDIA_INPUT_PLAYBACK_STARTED = "MediaInputPlaybackStarted"
    MEDIA_INPUT_PLAYBACK_ENDED = "MediaInputPlaybackEnded"
    MEDIA_INPUT_ACTION_TRIGGERED = "MediaInputActionTriggered"


@dataclass
class OBSConfig:
    """OBS WebSocket接続設定"""
    host: str = "localhost"
    port: int = 4455
    password: Optional[str] = None
    auto_reconnect: bool = True
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 10


@dataclass
class SceneItem:
    """シーンアイテム情報"""
    scene_item_id: int
    source_name: str
    source_type: str
    scene_item_index: int
    scene_item_enabled: bool
    scene_item_locked: bool
    scene_item_transform: dict = field(default_factory=dict)


@dataclass
class Scene:
    """シーン情報"""
    scene_name: str
    scene_index: int
    scene_uuid: Optional[str] = None


class OBSWebSocketClient:
    """OBS WebSocket 5.x クライアント"""
    
    RPC_VERSION = 1
    
    def __init__(self, config: Optional[OBSConfig] = None):
        self.config = config or OBSConfig()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._message_id = 0
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._event_handlers: dict[str, list[Callable]] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._shutdown = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None
    
    def _get_url(self) -> str:
        return f"ws://{self.config.host}:{self.config.port}"
    
    def _generate_message_id(self) -> str:
        self._message_id += 1
        return f"lobby-{self._message_id}"
    
    def _generate_auth_string(self, challenge: str, salt: str) -> str:
        """認証文字列を生成（obs-websocket 5.x認証）"""
        if not self.config.password:
            return ""
        
        # Step 1: SHA256(password + salt) -> base64
        secret_hash = hashlib.sha256(
            (self.config.password + salt).encode("utf-8")
        ).digest()
        secret_base64 = base64.b64encode(secret_hash).decode("utf-8")
        
        # Step 2: SHA256(secret_base64 + challenge) -> base64
        auth_hash = hashlib.sha256(
            (secret_base64 + challenge).encode("utf-8")
        ).digest()
        auth_base64 = base64.b64encode(auth_hash).decode("utf-8")
        
        return auth_base64
    
    async def connect(self) -> bool:
        """OBS WebSocketに接続"""
        if self._connected:
            logger.warning("Already connected to OBS")
            return True
        
        self._shutdown = False
        
        try:
            logger.info(f"Connecting to OBS at {self._get_url()}")
            self._ws = await websockets.connect(self._get_url())
            
            # Hello メッセージを受信
            hello_msg = await self._ws.recv()
            hello = json.loads(hello_msg)
            
            if hello.get("op") != 0:  # Hello = op 0
                logger.error(f"Unexpected message: {hello}")
                return False
            
            hello_data = hello.get("d", {})
            obs_version = hello_data.get("obsWebSocketVersion", "unknown")
            rpc_version = hello_data.get("rpcVersion", 1)
            logger.info(f"OBS WebSocket {obs_version} (RPC v{rpc_version})")
            
            # 認証が必要かチェック
            auth_data = hello_data.get("authentication")
            identify_payload = {"rpcVersion": self.RPC_VERSION}
            
            if auth_data:
                if not self.config.password:
                    logger.error("OBS requires authentication but no password provided")
                    return False
                
                challenge = auth_data["challenge"]
                salt = auth_data["salt"]
                identify_payload["authentication"] = self._generate_auth_string(challenge, salt)
                logger.debug("Authentication required, sending credentials")
            
            # Identify メッセージを送信
            await self._ws.send(json.dumps({
                "op": 1,  # Identify
                "d": identify_payload
            }))
            
            # Identified メッセージを受信
            identified_msg = await self._ws.recv()
            identified = json.loads(identified_msg)
            
            if identified.get("op") != 2:  # Identified = op 2
                logger.error(f"Authentication failed: {identified}")
                return False
            
            self._connected = True
            logger.info("Successfully connected and authenticated to OBS")
            
            # 受信ループを開始
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """OBS WebSocketから切断"""
        self._shutdown = True
        self._connected = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        logger.info("Disconnected from OBS")
    
    async def _receive_loop(self):
        """メッセージ受信ループ"""
        try:
            while self._connected and self._ws:
                try:
                    message = await self._ws.recv()
                    await self._handle_message(json.loads(message))
                except ConnectionClosed:
                    logger.warning("OBS WebSocket connection closed")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from OBS: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            self._connected = False
            if not self._shutdown and self.config.auto_reconnect:
                self._reconnect_task = asyncio.create_task(self._reconnect())
    
    async def _reconnect(self):
        """再接続を試行"""
        attempts = 0
        while not self._shutdown and attempts < self.config.max_reconnect_attempts:
            attempts += 1
            logger.info(f"Reconnecting to OBS (attempt {attempts}/{self.config.max_reconnect_attempts})")
            await asyncio.sleep(self.config.reconnect_delay)
            
            if await self.connect():
                logger.info("Reconnected to OBS successfully")
                return
        
        logger.error("Failed to reconnect to OBS after max attempts")
    
    async def _handle_message(self, message: dict):
        """受信メッセージを処理"""
        op = message.get("op")
        data = message.get("d", {})
        
        if op == 5:  # Event
            event_type = data.get("eventType")
            event_data = data.get("eventData", {})
            await self._dispatch_event(event_type, event_data)
        
        elif op == 7:  # RequestResponse
            request_id = data.get("requestId")
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if data.get("requestStatus", {}).get("result", False):
                    future.set_result(data.get("responseData", {}))
                else:
                    error = data.get("requestStatus", {})
                    future.set_exception(
                        OBSRequestError(
                            error.get("code", -1),
                            error.get("comment", "Unknown error")
                        )
                    )
    
    async def _dispatch_event(self, event_type: str, event_data: dict):
        """イベントをハンドラに配信"""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")
    
    def on_event(self, event_type: str | OBSEventType):
        """イベントハンドラを登録するデコレータ"""
        if isinstance(event_type, OBSEventType):
            event_type = event_type.value
        
        def decorator(func: Callable):
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func
        return decorator
    
    async def call(self, request_type: str, request_data: Optional[dict] = None) -> dict:
        """OBSにリクエストを送信"""
        if not self.is_connected:
            raise OBSNotConnectedError("Not connected to OBS")
        
        request_id = self._generate_message_id()
        
        message = {
            "op": 6,  # Request
            "d": {
                "requestType": request_type,
                "requestId": request_id,
            }
        }
        
        if request_data:
            message["d"]["requestData"] = request_data
        
        # レスポンス用のFutureを作成
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        try:
            await self._ws.send(json.dumps(message))
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise OBSRequestError(-1, f"Request {request_type} timed out")
    
    # ========== シーン操作 ==========
    
    async def get_scene_list(self) -> list[Scene]:
        """シーン一覧を取得"""
        response = await self.call("GetSceneList")
        scenes = []
        for i, scene in enumerate(response.get("scenes", [])):
            scenes.append(Scene(
                scene_name=scene["sceneName"],
                scene_index=i,
                scene_uuid=scene.get("sceneUuid")
            ))
        return scenes
    
    async def get_current_scene(self) -> str:
        """現在のシーン名を取得"""
        response = await self.call("GetCurrentProgramScene")
        return response.get("currentProgramSceneName", "")
    
    async def set_current_scene(self, scene_name: str):
        """シーンを切り替え"""
        await self.call("SetCurrentProgramScene", {"sceneName": scene_name})
        logger.info(f"Switched to scene: {scene_name}")
    
    # ========== シーンアイテム操作 ==========
    
    async def get_scene_items(self, scene_name: str) -> list[SceneItem]:
        """シーン内のアイテム一覧を取得"""
        response = await self.call("GetSceneItemList", {"sceneName": scene_name})
        items = []
        for item in response.get("sceneItems", []):
            items.append(SceneItem(
                scene_item_id=item["sceneItemId"],
                source_name=item["sourceName"],
                source_type=item.get("sourceType", ""),
                scene_item_index=item["sceneItemIndex"],
                scene_item_enabled=item["sceneItemEnabled"],
                scene_item_locked=item["sceneItemLocked"],
                scene_item_transform=item.get("sceneItemTransform", {})
            ))
        return items
    
    async def set_scene_item_enabled(
        self, scene_name: str, item_id: int, enabled: bool
    ):
        """シーンアイテムの表示/非表示を切り替え"""
        await self.call("SetSceneItemEnabled", {
            "sceneName": scene_name,
            "sceneItemId": item_id,
            "sceneItemEnabled": enabled
        })
    
    async def set_scene_item_transform(
        self, scene_name: str, item_id: int, transform: dict
    ):
        """シーンアイテムのトランスフォームを設定"""
        await self.call("SetSceneItemTransform", {
            "sceneName": scene_name,
            "sceneItemId": item_id,
            "sceneItemTransform": transform
        })
    
    # ========== 入力（ソース）操作 ==========
    
    async def get_input_settings(self, input_name: str) -> dict:
        """入力の設定を取得"""
        response = await self.call("GetInputSettings", {"inputName": input_name})
        return response.get("inputSettings", {})
    
    async def set_input_settings(self, input_name: str, settings: dict, overlay: bool = True):
        """入力の設定を変更"""
        await self.call("SetInputSettings", {
            "inputName": input_name,
            "inputSettings": settings,
            "overlay": overlay
        })
    
    async def set_input_mute(self, input_name: str, muted: bool):
        """入力のミュート状態を設定"""
        await self.call("SetInputMute", {
            "inputName": input_name,
            "inputMuted": muted
        })
    
    async def set_input_volume(self, input_name: str, volume_db: float):
        """入力の音量を設定（dB）"""
        await self.call("SetInputVolume", {
            "inputName": input_name,
            "inputVolumeDb": volume_db
        })
    
    # ========== 仮想カメラ ==========
    
    async def get_virtual_cam_status(self) -> bool:
        """仮想カメラの状態を取得"""
        response = await self.call("GetVirtualCamStatus")
        return response.get("outputActive", False)
    
    async def start_virtual_cam(self):
        """仮想カメラを開始"""
        await self.call("StartVirtualCam")
        logger.info("Virtual camera started")
    
    async def stop_virtual_cam(self):
        """仮想カメラを停止"""
        await self.call("StopVirtualCam")
        logger.info("Virtual camera stopped")
    
    async def toggle_virtual_cam(self) -> bool:
        """仮想カメラをトグル"""
        response = await self.call("ToggleVirtualCam")
        active = response.get("outputActive", False)
        logger.info(f"Virtual camera: {'active' if active else 'inactive'}")
        return active
    
    # ========== 録画 ==========
    
    async def get_record_status(self) -> dict:
        """録画状態を取得"""
        return await self.call("GetRecordStatus")
    
    async def start_record(self):
        """録画を開始"""
        await self.call("StartRecord")
        logger.info("Recording started")
    
    async def stop_record(self) -> str:
        """録画を停止（出力ファイルパスを返す）"""
        response = await self.call("StopRecord")
        output_path = response.get("outputPath", "")
        logger.info(f"Recording stopped: {output_path}")
        return output_path
    
    async def pause_record(self):
        """録画を一時停止"""
        await self.call("PauseRecord")
        logger.info("Recording paused")
    
    async def resume_record(self):
        """録画を再開"""
        await self.call("ResumeRecord")
        logger.info("Recording resumed")
    
    # ========== ストリーミング ==========
    
    async def get_stream_status(self) -> dict:
        """配信状態を取得"""
        return await self.call("GetStreamStatus")
    
    async def start_stream(self):
        """配信を開始"""
        await self.call("StartStream")
        logger.info("Streaming started")
    
    async def stop_stream(self):
        """配信を停止"""
        await self.call("StopStream")
        logger.info("Streaming stopped")
    
    async def toggle_stream(self) -> bool:
        """配信をトグル"""
        response = await self.call("ToggleStream")
        active = response.get("outputActive", False)
        logger.info(f"Streaming: {'active' if active else 'inactive'}")
        return active
    
    # ========== スクリーンショット ==========
    
    async def get_source_screenshot(
        self,
        source_name: str,
        image_format: str = "png",
        width: Optional[int] = None,
        height: Optional[int] = None,
        quality: int = 100
    ) -> str:
        """ソースのスクリーンショットを取得（base64）"""
        request_data = {
            "sourceName": source_name,
            "imageFormat": image_format,
            "imageCompressionQuality": quality
        }
        if width:
            request_data["imageWidth"] = width
        if height:
            request_data["imageHeight"] = height
        
        response = await self.call("GetSourceScreenshot", request_data)
        return response.get("imageData", "")


class OBSError(Exception):
    """OBS関連エラーの基底クラス"""
    pass


class OBSNotConnectedError(OBSError):
    """OBSに接続していない"""
    pass


class OBSRequestError(OBSError):
    """OBSリクエストエラー"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"OBS Error {code}: {message}")


# ========== Lobby統合用ヘルパー ==========

class LobbyOBSIntegration:
    """LobbyとOBSの統合レイヤー"""
    
    def __init__(self, obs_client: OBSWebSocketClient):
        self.obs = obs_client
        self._avatar_source_name: Optional[str] = None
        self._avatar_scene_name: Optional[str] = None
    
    async def setup_avatar_source(self, source_name: str, scene_name: str):
        """アバターソースを設定"""
        self._avatar_source_name = source_name
        self._avatar_scene_name = scene_name
        logger.info(f"Avatar source configured: {source_name} in scene {scene_name}")
    
    async def update_avatar_image(self, image_path: str):
        """アバター画像を更新（画像ソースの場合）"""
        if not self._avatar_source_name:
            logger.warning("Avatar source not configured")
            return
        
        await self.obs.set_input_settings(
            self._avatar_source_name,
            {"file": image_path}
        )
    
    async def show_avatar(self):
        """アバターを表示"""
        if not self._avatar_source_name or not self._avatar_scene_name:
            return
        
        items = await self.obs.get_scene_items(self._avatar_scene_name)
        for item in items:
            if item.source_name == self._avatar_source_name:
                await self.obs.set_scene_item_enabled(
                    self._avatar_scene_name, item.scene_item_id, True
                )
                break
    
    async def hide_avatar(self):
        """アバターを非表示"""
        if not self._avatar_source_name or not self._avatar_scene_name:
            return
        
        items = await self.obs.get_scene_items(self._avatar_scene_name)
        for item in items:
            if item.source_name == self._avatar_source_name:
                await self.obs.set_scene_item_enabled(
                    self._avatar_scene_name, item.scene_item_id, False
                )
                break
    
    async def set_avatar_position(self, x: float, y: float):
        """アバターの位置を設定"""
        if not self._avatar_source_name or not self._avatar_scene_name:
            return
        
        items = await self.obs.get_scene_items(self._avatar_scene_name)
        for item in items:
            if item.source_name == self._avatar_source_name:
                await self.obs.set_scene_item_transform(
                    self._avatar_scene_name,
                    item.scene_item_id,
                    {"positionX": x, "positionY": y}
                )
                break
    
    async def set_avatar_scale(self, scale_x: float, scale_y: Optional[float] = None):
        """アバターのスケールを設定"""
        if scale_y is None:
            scale_y = scale_x
        
        if not self._avatar_source_name or not self._avatar_scene_name:
            return
        
        items = await self.obs.get_scene_items(self._avatar_scene_name)
        for item in items:
            if item.source_name == self._avatar_source_name:
                await self.obs.set_scene_item_transform(
                    self._avatar_scene_name,
                    item.scene_item_id,
                    {"scaleX": scale_x, "scaleY": scale_y}
                )
                break
    
    async def start_recording_session(self):
        """録画セッションを開始（仮想カメラ + 録画）"""
        await self.obs.start_virtual_cam()
        await self.obs.start_record()
        logger.info("Recording session started (virtual cam + recording)")
    
    async def stop_recording_session(self) -> str:
        """録画セッションを停止"""
        output_path = await self.obs.stop_record()
        await self.obs.stop_virtual_cam()
        logger.info("Recording session stopped")
        return output_path
