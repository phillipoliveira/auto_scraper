import time
from src.models.pull import Pull
from src.common.database import Database
from datetime import datetime

class ScheduledTasks(object):

    @staticmethod
    def update_posts(pulls):
        if len(pulls) == 0:
            print('no posts!')
        else:
            for pull in pulls:
                print('checking for expired posts...')
                pull.delete_expired_posts()
                print('updating posts...')
                pull.generate_kijiji_posts_data(new_or_update='update')
                pull.generate_autotrader_posts_data(new_or_update='update')
            print("posts refreshed!")
            print(datetime.utcnow())
        return

    @classmethod
    def update_posts_loop(cls):
        Database.initialize()

        while True:
            pulls = Pull.all_pulls()
            cls.update_posts(pulls)
            time.sleep(3600)
