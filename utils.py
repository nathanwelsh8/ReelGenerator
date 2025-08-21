from datetime import datetime, timezone

class DialougeStatus:

    NEW = 'NEW'
    INPROGRESS = 'INPROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    UPLOADED = 'UPLOADED'



class ProxyHttpConstants:

    ACCEPT_HEADER = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8.application/json'
    USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_3 like Mac OS X) AppleWebKit/603.3.8 (KHTML, like Gecko) Mobile/14G60 MicroMessenger/6.5.19 NetType/4G Language/zh_TW'


def get_datetime_str() -> str:
    """Return a UTC timestamp string for metadata fields."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S%z')