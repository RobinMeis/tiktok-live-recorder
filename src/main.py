# print banner
from utils.utils import banner

banner()

# check and install dependencies
from utils.dependencies import check_and_install_dependencies

check_and_install_dependencies()

# check for updates
from check_updates import check_updates

if check_updates():
    exit()

import sys
import os

from utils.args_handler import validate_and_parse_args
from utils.utils import read_cookies
from utils.logger_manager import logger

from core.tiktok_recorder import TikTokRecorder
from utils.enums import TikTokError
from utils.custom_exceptions import LiveNotFound, ArgsParseError, \
    UserLiveException, IPBlockedByWAF, TikTokException

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("hi")
def main():
    try:
        args, mode = validate_and_parse_args()

        # read cookies from file
        cookies = read_cookies()

        TikTokRecorder(
            url=args.url,
            user=args.user,
            room_id=args.room_id,
            mode=mode,
            cookies=cookies,
            proxy=args.proxy,
            output=args.output,
            duration=args.duration,
            use_telegram=args.telegram,
        ).run()

    except ArgsParseError as ex:
        logger.error(ex)

    except LiveNotFound as ex:
        logger.error(ex)

    except IPBlockedByWAF:
        logger.error(TikTokError.WAF_BLOCKED)

    except UserLiveException as ex:
        logger.error(ex)

    except TikTokException as ex:
        logger.error(ex)

    except Exception as ex:
        logger.error(ex)


if __name__ == "__main__":
    main()
