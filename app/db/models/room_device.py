from sqlalchemy import Column, BigInteger, Integer, ForeignKey
from app.db.base import Base

class RoomDevice(Base):
    __tablename__ = "room_device"

    id = Column(BigInteger, primary_key=True, index=True)
    room_id = Column(BigInteger, ForeignKey("room.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id = Column(BigInteger, ForeignKey("device.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order = Column(Integer, default=0)

    def __repr__(self):
        return f"<RoomDevice(id={self.id}, room_id={self.room_id}, device_id={self.device_id}, sort_order={self.sort_order})>"
