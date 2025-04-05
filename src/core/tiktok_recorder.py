import os
import time
from http.client import HTTPException

from requests import RequestException

from core.tiktok_api import TikTokAPI
from utils.logger_manager import logger
from core.video_management import VideoManagement
from upload.telegram import Telegram
from utils.custom_exceptions import LiveNotFound, UserLiveException, \
    TikTokException
from utils.enums import Mode, Error, TimeOut, TikTokError


class TikTokRecorder:

    def __init__(
        self,
        url,
        user,
        room_id,
        mode,
        cookies,
        proxy,
        output,
        duration,
        use_telegram,
    ):
        # TikTok Data
        self.url = url
        self.user = user
        self.room_id = room_id

        # Tool Settings
        self.mode = mode
        self.duration = duration
        self.output = output

        # Upload Settings
        self.use_telegram = use_telegram

        # Setup TikTok API client
        self.client = TikTokAPI(proxy=proxy, cookies=cookies)

        # Check if the user's country is blacklisted
        self.check_country_blacklisted()

        # Get live information based on the provided user data
        if self.url:
            self.user, self.room_id = \
                self.client.get_room_and_user_from_url(self.url)

        if not self.user:
            self.user = self.client.get_user_from_room_id(self.room_id)

        if not self.room_id:
            self.room_id = self.client.get_room_id_from_user(self.user)

        logger.info(f"USERNAME: {self.user}" + ("\n" if not self.room_id else ""))
        if not self.room_id:
            if mode == Mode.MANUAL:
                raise UserLiveException(TikTokError.USER_NOT_CURRENTLY_LIVE)
        else:
            logger.info(f"ROOM_ID:  {self.room_id}" + ("\n" if not self.client.is_room_alive(self.user) else ""))

        # If proxy is provided, set up the HTTP client without the proxy
        if proxy:
            self.client = TikTokAPI(proxy=None, cookies=cookies)

    def run(self):
        """
        runs the program in the selected mode. 
        
        If the mode is MANUAL, it checks if the user is currently live and
        if so, starts recording.
        
        If the mode is AUTOMATIC, it continuously checks if the user is live
        and if not, waits for the specified timeout before rechecking.
        If the user is live, it starts recording.
        """
        if self.mode == Mode.MANUAL:
            self.manual_mode()

        if self.mode == Mode.AUTOMATIC:
            self.automatic_mode()

    def manual_mode(self):
        if not self.client.is_room_alive(self.room_id):
            raise UserLiveException(TikTokError.USER_NOT_CURRENTLY_LIVE)

        self.start_recording()

    def automatic_mode(self):
        while True:
            try:
                self.room_id = self.client.get_room_id_from_user(self.user)

                if self.room_id == '' or not self.client.is_room_alive(self.room_id):
                    raise UserLiveException(TikTokError.USER_NOT_CURRENTLY_LIVE)

                self.start_recording()

            except UserLiveException as ex:
                logger.info(ex)
                logger.info(f"Waiting {TimeOut.AUTOMATIC_MODE} minutes before recheck\n")
                time.sleep(TimeOut.AUTOMATIC_MODE * TimeOut.ONE_MINUTE)

            except ConnectionError:
                logger.error(Error.CONNECTION_CLOSED_AUTOMATIC)
                time.sleep(TimeOut.CONNECTION_CLOSED * TimeOut.ONE_MINUTE)

            except Exception as ex:
                logger.error(f"Unexpected error: {ex}\n")

    def start_recording(self):
        """
        Start recording live
        """
        live_url = self.client.get_live_url(self.room_id)
        if not live_url:
            raise LiveNotFound(TikTokError.RETRIEVE_LIVE_URL)

        current_date = time.strftime("%Y.%m.%d_%H-%M-%S", time.localtime())

        if isinstance(self.output, str) and self.output != '':
            if not (self.output.endswith('/') or self.output.endswith('\\')):
                if os.name == 'nt':
                    self.output = self.output + "\\"
                else:
                    self.output = self.output + "/"

        output = f"{self.output if self.output else ''}TK_{self.user}_{current_date}_flv.mp4"

        if self.duration:
            logger.info(f"Started recording for {self.duration} seconds ")
        else:
            logger.info("Started recording...")

        BUFFER_SIZE = 3 * (1024 * 1024)  # 3 MB buffer
        buffer = bytearray()

        logger.info("[PRESS CTRL + C ONCE TO STOP]")
        with open(output, "wb") as out_file:
            stop_recording = False
            while not stop_recording:
                try:
                    if not self.client.is_room_alive(self.room_id):
                        logger.info("User is no longer live. Stopping recording.")
                        break

                    response = self.httpclient.get(live_url, stream=True)
                    start_time = time.time()
                    for chunk in response.iter_content(chunk_size=None):
                        if not chunk or len(chunk) == 0:
                            continue

                        buffer.extend(chunk)
                        if len(buffer) >= BUFFER_SIZE:
                            out_file.write(buffer)
                            buffer.clear()

                        elapsed_time = time.time() - start_time
                        if self.duration is not None and elapsed_time >= self.duration:
                            stop_recording = True
                            break

                except ConnectionError:
                    if self.mode == Mode.AUTOMATIC:
                        logger.error(Error.CONNECTION_CLOSED_AUTOMATIC)
                        time.sleep(TimeOut.CONNECTION_CLOSED * TimeOut.ONE_MINUTE)

                except (RequestException, HTTPException):
                    time.sleep(2)

                except KeyboardInterrupt:
                    logger.info("Recording stopped by user.")
                    stop_recording = True

                except Exception as ex:
                    logger.error(f"Unexpected error: {ex}\n")
                    stop_recording = True

                finally:
                    if buffer:
                        out_file.write(buffer)
                        buffer.clear()

        logger.info(f"Recording finished: {output}\n")
        VideoManagement.convert_flv_to_mp4(output)

        if self.use_telegram:
            Telegram().upload(output.replace('_flv.mp4', '.mp4'))

    def check_country_blacklisted(self):
        is_blacklisted = self.client.is_country_blacklisted()
        if not is_blacklisted:
            return False

        if self.room_id is None:
            raise TikTokException(TikTokError.COUNTRY_BLACKLISTED)

        if self.mode == Mode.AUTOMATIC:
            raise TikTokException(TikTokError.COUNTRY_BLACKLISTED_AUTO_MODE)
