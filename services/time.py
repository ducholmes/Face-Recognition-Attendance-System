from datetime import date
import time

# Thông tin timestamp
def get_timestamp():
    return f"{int(time.time())}"

def get_date():
    return f"{date.today()}"