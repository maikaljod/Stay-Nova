"""WTForms form definitions with server-side validation.

Flask-WTF automatically wires CSRF protection into every form here.
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, SelectField,
    IntegerField, DecimalField, DateField, TextAreaField, HiddenField,
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, ValidationError
)

PASSWORD_RULE = Regexp(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$",
    message="Password must be at least 8 characters and include an uppercase letter, "
            "a lowercase letter, and a number.",
)

PHONE_RULE = Regexp(r"^[0-9+\-\s()]{7,20}$", message="Enter a valid phone number.")


class RegistrationForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=60)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=60)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), PHONE_RULE])
    password = PasswordField("Password", validators=[DataRequired(), PASSWORD_RULE])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = SelectField(
        "Remember me", choices=[("0", "No"), ("1", "Yes")], default="0", validators=[Optional()]
    )
    submit = SubmitField("Log in")


class SearchForm(FlaskForm):
    city = StringField("Destination", validators=[Optional(), Length(max=100)])
    check_in = DateField("Check-in", validators=[Optional()])
    check_out = DateField("Check-out", validators=[Optional()])
    guests = IntegerField("Guests", validators=[Optional(), NumberRange(min=1, max=20)], default=2)
    submit = SubmitField("Search")


class BookingForm(FlaskForm):
    room_id = HiddenField(validators=[DataRequired()])
    check_in = DateField("Check-in", validators=[DataRequired()])
    check_out = DateField("Check-out", validators=[DataRequired()])
    guests = IntegerField("Guests", validators=[DataRequired(), NumberRange(min=1, max=20)])
    submit = SubmitField("Confirm booking")

    def validate_check_out(self, field):
        if self.check_in.data and field.data and field.data <= self.check_in.data:
            raise ValidationError("Check-out date must be after check-in date.")


class HotelForm(FlaskForm):
    name = StringField("Hotel name", validators=[DataRequired(), Length(max=150)])
    city = StringField("City", validators=[DataRequired(), Length(max=100)])
    address = StringField("Address", validators=[DataRequired(), Length(max=255)])
    star_rating = IntegerField("Star rating", validators=[DataRequired(), NumberRange(min=1, max=5)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    image_url = StringField("Image URL", validators=[Optional(), Length(max=500)])
    amenities = StringField("Amenities (comma separated)", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Add hotel")


class RoomForm(FlaskForm):
    room_type = StringField("Room type", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    price_per_night = DecimalField("Price per night", validators=[DataRequired(), NumberRange(min=0)])
    capacity = IntegerField("Capacity", validators=[DataRequired(), NumberRange(min=1, max=20)])
    total_rooms = IntegerField("Total rooms available", validators=[DataRequired(), NumberRange(min=1)])
    image_url = StringField("Image URL", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Add room")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField("New password", validators=[DataRequired(), PASSWORD_RULE])
    confirm_new_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Update password")
