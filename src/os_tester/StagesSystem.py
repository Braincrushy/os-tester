
import sys
from os import path, remove
from time import sleep, time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssimFunc

from os_tester.debug_plot import debugPlot
from os_tester.stages import stage, stages, subpath
from os_tester.IAction import IAction

class StagesSystem:
    """
    A wrapper around a qemu libvirt VM that handles the live time and stage execution.
    """

    uuid: str
    debugPlt: bool
    machine: IAction

    debugPlotObj: debugPlot

    def __init__(
        self,
        machine: IAction,
        uuid: str,
        debugPlt: bool = False,
    ):
        self.machine = machine
        self.uuid = uuid
        self.debugPlt = debugPlt
        if self.debugPlt:
            self.debugPlotObj = debugPlot()

    def __perform_stage_actions(self, stageObj: stage) -> None:
        """
        Performs all stage actions (mouse_move, keyboard_key, reboot, ...) on the current VM.

        Args:
            stageObj (stage): The stage the actions should be performed for.
        """
        for action in stageObj.actions:
            if "mouse_move" in action:
                self.machine.__send_mouse_move_action(action["mouse_move"])
            elif "mouse_click" in action:
                self.machine.__send_mouse_click_action(action["mouse_click"])
            elif "keyboard_key" in action:
                self.machine.__send_keyboard_key_action(action["keyboard_key"])
            elif "keyboard_text" in action:
                self.machine.__send_keyboard_text_action(action["keyboard_text"])
            elif "command" in action:
                self.machine.__send_keyboard_text_action(action["command"])
            else:
                raise Exception(f"Invalid stage action: {action}")

    def __img_mse(
        self,
        curImg: cv2.typing.MatLike,
        refImg: cv2.typing.MatLike,
    ) -> Tuple[float, cv2.typing.MatLike]:
        """
        Calculates the mean square error between two given images.
        Both images have to have the same size.

        Args:
            curImg (cv2.typing.MatLike): The current image taken from the VM.
            refImg (cv2.typing.MatLike): The reference image we are awaiting.

        Returns:
            Tuple[float, cv2.typing.MatLike]: A tuple of the mean square error and the image diff.
        """
        # Compute the difference
        imgDif: cv2.typing.MatLike = cv2.subtract(curImg, refImg)
        err = np.sum(imgDif**2)

        # Compute Mean Squared Error
        h, w = curImg.shape[:2]
        mse = err / (float(h * w))

        mse = min(
            mse,
            10,
        )  # Values over 10 do not make sense for our case and it makes it easier to plot it
        return mse, imgDif

    def __comp_images(
        self,
        curImg: cv2.typing.MatLike,
        refImg: cv2.typing.MatLike,
    ) -> Tuple[float, float, cv2.typing.MatLike]:
        """
        Compares the provided images and calculates the mean square error and structural similarity index.
        Based on: https://www.tutorialspoint.com/how-to-compare-two-images-in-opencv-python

        Args:
            curImg (cv2.typing.MatLike): The current image taken from the VM.
            refImg (cv2.typing.MatLike): The reference image we are awaiting.

        Returns:
            Tuple[float, float, cv2.typing.MatLike]: A tuple consisting of the mean square error, structural similarity index and a image diff of both images.
        """
        # Get the dimensions of the original image
        hRef, wRef = refImg.shape[:2]

        # Resize the reference image to match the original image's dimensions
        curImgResized = cv2.resize(curImg, (wRef, hRef))

        mse: float
        difImg: cv2.typing.MatLike
        mse, difImg = self.__img_mse(curImgResized, refImg)

        # Compute SSIM
        ssimIndex: float = ssimFunc(curImgResized, refImg, channel_axis=-1)

        return (mse, ssimIndex, difImg)

    def __wait_for_stage_done(self, stageObj: stage) -> None:
        """
        Returns once the given stages reference image is reached.

        Args:
            stageObj (stage): The stage we want to await for.
        """
        timeoutinS = stageObj.timeoutS
        start = time()
        refImgList = list()
        for subpath in stageObj.pathsList:
            refImgPath: str = subpath.checkFile
            if not path.exists(refImgPath):
                print(f"Stage ref image file '{refImgPath}' not found!")
                sys.exit(2)

            if not path.isfile(refImgPath):
                print(f"Stage ref image file '{refImgPath}' is no file!")
                sys.exit(3)
                
            refImgList.append(cv2.imread(refImgPath))
        while True:
            curImgPath: str = f"/tmp/{self.uuid}_check.png"
            self.machine.take_screenshot(curImgPath)
            print("ScreenShoot taken.")
            curImg: cv2.typing.MatLike = cv2.imread(curImgPath)

            mse: float
            ssimIndex: float
            difImg: cv2.typing.MatLike
            
            resultindex: int = -1
            for index, refImg in enumerate(refImgList, start=0):
                mse, ssimIndex, difImg = self.__comp_images(curImg, refImg)

                same: float = 1 if mse < subpath.checkMseLeq and ssimIndex > subpath.checkSsimGeq else 0
                print(f"MSE: {mse}, SSIM: {ssimIndex}, Images Same: {same}")
                if self.debugPlt:
                    self.debugPlotObj.update_plot(refImg, curImg, difImg, mse, ssimIndex, same)
                
                # break if a image was found
                if same >= 1:
                    resultindex = index
                    break
                
            if resultindex != -1:
                print(f"path number: {index}")
                return stageObj.pathsList[resultindex]
            
            # if timeout is exided
            elif start + timeoutinS >= time():
                print(f"timeout was called after {timeoutinS}")
                exit(5)
                
            sleep(0.25)

    def __run_stage(self, stageObj: stage) -> str:
        """
        1. Awaits until we reach the current stage reference image.
        2. Executes all actions defined by this stage.

        Args:
            stageObj (stage): The stage to execute/await for the image.
        Returns:
            str: with the name of the next requested Stage
        """
        start: float = time()
        print(f"Running stage '{stageObj.name}'.")

        subPath: subpath = self.__wait_for_stage_done(stageObj)
        self.__perform_stage_actions(stageObj)

        duration: float = time() - start
        print(f"Stage '{stageObj.name}' finished after {duration}s. Next Stage is: '{subPath.nextStage}'")
        
        return subPath.nextStage

    def run_stages(self, stagesObj: stages) -> None:
        """
        Executes all stages defined for the current PC and awaits every stage to finish before returning.
        If no name with requested StageName found exit with error
        """
        nextStage = stagesObj.stagesList[0]
        while True:
            nextStageName = self.__run_stage(nextStage)
            # if nextStageName is None exit program
            if nextStageName == "None":
                break
            for stage in stagesObj.stagesList:
                # if the expected next Stage name is found break
                if stage.name == nextStageName:
                    nextStage = stage
                    break
                else:
                    print(f"No Stage named {nextStageName} was found ")
                    exit(10)
