import datetime


class Tools:

    def __init__(self):
        pass

    def get_current_time(self):
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
