from sqlalchemy import Integer, String, Table
from typing import Optional
from sqlalchemy.orm import Mapped, DeclarativeBase
from sqlalchemy.orm import mapped_column
from configmanager import config

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = config['db']['users_table']

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(60), unique=True)
    first_name: Mapped[str] = mapped_column(String(30))
    last_name: Mapped[str] = mapped_column(String(30))
    middle_name: Mapped[str] = mapped_column(String(30))
    tel: Mapped[str] = mapped_column(String(30))
    position: Mapped[Optional[str]] = mapped_column(String(60))
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    office_number: Mapped[Optional[int]] = mapped_column(Integer, unique=True)

    def __repr__(self):
        return f"User(tg_id:{self.telegram_id!r}, username={self.username!r}, name={self.first_name!r}," \
               f" second_name={self.last_name!r}, tel={self.tel!r})"

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}, " \
               f"tg: @{self.username}, " \
               f"tel: {self.tel}"
