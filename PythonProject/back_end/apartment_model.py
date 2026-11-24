from database import db


class Apartment(db.Model):
    __tablename__ = "apartments"

    # Сохраняем исходные ID: yola-01, yola-02 и т.д.
    id = db.Column(db.String(80), primary_key=True)

    city = db.Column(db.String(120), nullable=False)
    rooms = db.Column(db.Integer, nullable=False)
    price = db.Column(db.BigInteger, nullable=False)
    area = db.Column(db.Float, nullable=False)

    building_condition = db.Column(db.String(255), nullable=True)
    metro_note = db.Column(db.Text, nullable=True)

    kindergarten_minutes = db.Column(db.Integer, nullable=True)
    school_minutes = db.Column(db.Integer, nullable=True)
    center_km = db.Column(db.Float, nullable=True)
    metro_minutes = db.Column(db.Integer, nullable=True)

    # Пока все записи демонстрационные.
    source = db.Column(
        db.String(50),
        nullable=False,
        default="demo"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "city": self.city,
            "rooms": self.rooms,
            "price": self.price,
            "area": self.area,
            "building_condition": self.building_condition,
            "metro_note": self.metro_note,
            "kindergarten_minutes": self.kindergarten_minutes,
            "school_minutes": self.school_minutes,
            "center_km": self.center_km,
            "metro_minutes": self.metro_minutes,
            "source": self.source
        }
