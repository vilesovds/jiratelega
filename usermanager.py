from sqlalchemy import and_, create_engine, inspect, select, update
from sqlalchemy.orm import sessionmaker, Session
from models import Base, User
import pandas as pd


class UserManager:
    def __init__(self, db_url="sqlite:///users.db", users_table='users'):
        self.engine = create_engine(db_url)
        if not inspect(self.engine).has_table(users_table):
            Base.metadata.create_all(self.engine)

    def search_user(self, tel=None, telegram_id=None):
        if telegram_id:
            stmt = select(User).where(User.telegram_id == telegram_id)
        else:
            stmt = select(User).where(User.tel == tel)

        with Session(self.engine) as session:
            result = session.execute(stmt).one_or_none()
            res = result[0] if result else None
        return res

    def get_user(self, telegram_id):
        stmt = select(User).where(User.telegram_id == telegram_id)
        with Session(self.engine) as session:
            result = session.execute(stmt)
            user_tuple = result.one_or_none()
            user = user_tuple[0] if user_tuple else None
        return str(user) if user else 'Noname'

    def get_user_name(self, telegram_id):
        stmt = select(User).where(User.telegram_id == telegram_id)
        with Session(self.engine) as session:
            result = session.execute(stmt)
            user = result.one_or_none()
        return user[0].first_name if user else 'Noname'

    def get_user_email(self, telegram_id):
        stmt = select(User).where(User.telegram_id == telegram_id)
        with Session(self.engine) as session:
            result = session.execute(stmt)
            user = result.one_or_none()
        return user[0].email if user else None

    def is_authorized_user(self, telegram_id):
        stmt = select(User).where(User.telegram_id == int(telegram_id))
        with Session(self.engine) as session:
            result = session.execute(stmt)
            res = True if result.one_or_none() else False
        return res

    def authorize_user(self, phone_number, telegram_id, username=None):
        stmt = select(User).where(User.tel == phone_number)
        with Session(self.engine) as session:
            result = session.execute(stmt).one_or_none()
            if result:
                user = result[0]
                user.telegram_id = int(telegram_id)
                user.username = username
                session.commit()
            else:
                return False
        return True

    def _create_user(self, user_dict):
        last_name, first_name, middle_name = user_dict['fio'].split(' ')
        with Session(self.engine) as session:
            user1 = User(
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                tel=user_dict['tel'],
                email=user_dict['email'],
                position=user_dict['position'],
                office_number=user_dict['office_number']
            )
            session.add(user1)
            session.commit()

    def delete_user(self, tel):
        with Session(self.engine) as session:
            session.query(User).filter(User.tel == tel).delete()
            session.commit()

    def sync(self, filename):
        # Load the xlsx file
        excel_data = pd.read_excel(
            filename,
            names=['n', 'fio', 'office_number', 'position', 'tel', 'email'],
            dtype=str
        )
        print(excel_data)
        for index, user in excel_data.iterrows():
            if not self.search_user(tel=user['tel']):
                self._create_user(user)
                print(f"added user {user['fio']}")

        # get all tels
        stmt = select(User.tel)
        with Session(self.engine) as session:
            result = session.execute(stmt).all()
        current_numbers = set([item[0] for item in result])

        number_from_file = set(excel_data['tel'])
        for_delete = current_numbers - number_from_file
        print(f'to delete: {for_delete}')
        for tel in list(for_delete):
            self.delete_user(tel)
        print(f"done")


if __name__ == "__main__":
    from configmanager import config
    um = UserManager(config['db']['url'], config['db']['users_table'])
    um.sync('users.xlsx')
