from typing import Any, Dict, Optional, Tuple
from time import sleep, time
import json
from os import path, remove
import libvirt
import libvirt_qemu
from contextlib import suppress
import cv2

from os_tester.IAction import IAction

class newvm(IAction):  
    """
    A wrapper around a qemu libvirt VM that handles the live time and stage execution.
    """

    conn: libvirt.virConnect
    uuid: str
    vmDom: Optional[libvirt.virDomain]

    def __init__(
        self,
        conn: libvirt.virConnect,
        uuid: str,
    ):
        self.conn = conn
        self.uuid = uuid
        self.vmDom = None
    
    def try_load(self) -> bool:
        """
        Tries to lookup and load the qemu/libvirt VM via 'self.uuid' and returns the result.

        Returns:
            bool: True: The VM exists and was loaded successfully.
        """
        with suppress(libvirt.libvirtError):
            self.vmDom = self.conn.lookupByUUIDString(self.uuid)
            return self.vmDom is not None
        return False
        
        
    def __get_screen_size(self) -> Tuple[int, int]:
        """
        Helper function returning the VM screen size by taking a screenshoot and using this image than as width and height.

        Returns:
            Tuple[int, int]: width and height
        """
        filePath: str = f"/tmp/{self.uuid}_screen_size.png"
        self.take_screenshot(filePath)

        img: cv2.typing.MatLike = cv2.imread(filePath)

        # Delete screen shoot again since we do not need it any more
        remove(filePath)

        h, w = img.shape[:2]
        return (w, h)

    def __send_action(self, cmdDict: Dict[str, Any]) -> Optional[Any]:
        """
        Sends a qemu monitor command to the VM.
        Ref: https://en.wikibooks.org/wiki/QEMU/Monitor

        Args:
            cmdDict (Dict[str, Any]): A dict defining the qemu monitor command.

        Returns:
            Optional[Any]: The qemu execution result.
        """
        cmd: str = json.dumps(cmdDict)
        try:
            response: Any = libvirt_qemu.qemuMonitorCommand(self.vmDom, cmd, 0)
            print(f"Action response: {response}")
            return response
        except libvirt.libvirtError as e:
            print(f"Failed to send action event: {e}")
        return None

    def __send_keyboard_text_action(self, keyboardText: Dict[str, Any]) -> None:
        """
        Sends a row of key press events via the qemu monitor.

        Args:
            keyboardText (Dict[str, Any]): The dict defining the text to send and how.
        """
        for c in keyboardText["value"]:
            cmdDictDown: Dict[str, Any] = {
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {
                            "type": "key",
                            "data": {
                                "down": True,
                                "key": {"type": "qcode", "data": c},
                            },
                        },
                    ],
                },
            }
            self.__send_action(cmdDictDown)
            sleep(keyboardText["duration_s"])

            cmdDictUp: Dict[str, Any] = {
                "execute": "input-send-event",
                "arguments": {
                    "events": [
                        {
                            "type": "key",
                            "data": {
                                "down": False,
                                "key": {"type": "qcode", "data": c},
                            },
                        },
                    ],
                },
            }
            self.__send_action(cmdDictUp)
            sleep(keyboardText["duration_s"])

    def send_keyboard_key_action(self, keyboardKey: Dict[str, Any]) -> None:
        """
        Performs a keyboard key press action via the qemu monitor.

        Args:
            keyboardKey (Dict[str, Any]): The dict defining the keyboard key to send and how.
        """
        cmdDictDown: Dict[str, Any] = {
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "data": {
                            "down": True,
                            "key": {"type": "qcode", "data": keyboardKey["value"]},
                        },
                    },
                ],
            },
        }
        self.__send_action(cmdDictDown)
        sleep(keyboardKey["duration_s"])

        cmdDictUp: Dict[str, Any] = {
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "key",
                        "data": {
                            "down": False,
                            "key": {"type": "qcode", "data": keyboardKey["value"]},
                        },
                    },
                ],
            },
        }
        self.__send_action(cmdDictUp)
        sleep(keyboardKey["duration_s"])

    def send_mouse_move_action(self, mouseMove: Dict[str, Any]) -> None:
        """
        Performs a mouse move action via the qemu monitor.

        Args:
            mouseMove (Dict[str, Any]): The dict defining the mouse move action.
        """
        w: int
        h: int
        w, h = self.__get_screen_size()

        cmdDict: Dict[str, Any] = {
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "abs",
                        "data": {
                            "axis": "x",
                            "value": 0,
                        },
                    },
                    {
                        "type": "abs",
                        "data": {"axis": "y", "value": 0},
                    },
                    {
                        "type": "rel",
                        "data": {
                            "axis": "x",
                            "value": int(w * mouseMove["x_rel"]),
                        },
                    },
                    {
                        "type": "rel",
                        "data": {"axis": "y", "value": int(h * mouseMove["y_rel"])},
                    },
                ],
            },
        }
        self.__send_action(cmdDict)
        sleep(mouseMove["duration_s"])

    def send_mouse_click_action(self, mouseClick: Dict[str, Any]) -> None:
        """
        Performs a mouse click action via the qemu monitor.

        Args:
            mouseMove (Dict[str, Any]): The dict defining the mouse click action.
        """
        cmdDictDown: Dict[str, Any] = {
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "btn",
                        "data": {"down": True, "button": mouseClick["value"]},
                    },
                ],
            },
        }
        self.__send_action(cmdDictDown)
        sleep(mouseClick["duration_s"])

        cmdDictUp: Dict[str, Any] = {
            "execute": "input-send-event",
            "arguments": {
                "events": [
                    {
                        "type": "btn",
                        "data": {"down": False, "button": mouseClick["value"]},
                    },
                ],
            },
        }
        self.__send_action(cmdDictUp)
        sleep(mouseClick["duration_s"])
        
        
    def send_commandk_action(self, command: Dict[str, Any]) -> None:
        """
        Performs a mouse click action via the qemu monitor.

        Args:
            mouseMove (Dict[str, Any]): The dict defining the mouse click action.
        """
        if command["command"] == "reboot":
            assert self.vmDom
            self.vmDom.reboot()
        
    def destroy(self) -> None:
        """
        Tell qemu/libvirt to destroy the VM defined by 'self.uuid'.

        Raises:
            Exception: In case the VM has not been loaded before via e.g. try_load(...).
        """
        if not self.vmDom:
            raise Exception("Can not destroy vm. Use try_load or create first!")

        self.vmDom.destroy()

    def create(self, vmXml: str) -> None:
        """
        Creates a new libvirt/qemu VM based on the provided libvirt XML string.
        Ref: https://libvirt.org/formatdomain.html

        Args:
            vmXml (str): The libvirt XML string defining the VM. Ref: https://libvirt.org/formatdomain.html

        Raises:
            Exception: In case the VM with 'self.uuid' already exists.
        """
        with suppress(libvirt.libvirtError):
            if self.conn.lookupByUUIDString(self.uuid):
                raise Exception(
                    f"Can not create vm with UUID '{self.uuid}'. VM already exists. Destroy first!",
                )
                
    def take_screenshot(self, targetPath: str) -> None:
        """
        Takes a screenshoot of the current VM output and stores it as a file.

        Args:
            targetPath (str): Where to store the screenshoot at.
        """
        stream: libvirt.virStream = self.conn.newStream()

        assert self.vmDom
        imgType: Any = self.vmDom.screenshot(stream, 0)

        with open(targetPath, "wb") as f:
            streamBytes = stream.recv(262120)
            while streamBytes != b"":
                f.write(streamBytes)
                streamBytes = stream.recv(262120)

        print(f"Screenshot saved as type '{imgType}' under '{targetPath}'.")
        stream.finish()