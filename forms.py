# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, SelectField
from wtforms.validators import DataRequired, NumberRange, Optional, Length, Regexp, ValidationError # Added Optional, Length, Regexp

# --- Consolidated CSRFOnlyForm ---
class CSRFOnlyForm(FlaskForm):
    """A simple form to just render a CSRF token."""
    # submit = SubmitField('Submit') # Optional, if you need a visible submit button for simple CSRF
    pass
# --- End of consolidated CSRFOnlyForm ---

class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class CreateDrawForm(FlaskForm):
    name = StringField('Draw Name', validators=[DataRequired()])
    total_tickets = IntegerField('Number of Tickets Available', validators=[DataRequired(), NumberRange(min=1)])
    ticket_price = FloatField('Ticket Price ($)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Create Draw')

class ReserveTicketForm(FlaskForm):
    ticket_number = SelectField(
        'Ticket Number',coerce=str,
       choices=[],                # Will be populated dynamically
        validators=[DataRequired(message="Please select a ticket number")],
       # coerce=int                 # Convert selected value to int automatically
    )
    user_telegram_id = StringField('Telegram ID', validators=[DataRequired()])
    user_username = StringField('Telegram Username', validators=[DataRequired()])
    submit = SubmitField('Reserve Ticket')
    # You can add custom validation if needed for unique telegram_id or username
    # For example, to validate telegram_id is not already linked to another user
    # def validate_user_telegram_id(self, field):
    #     from .models import User # Import here to avoid circular imports
    #     user = User.query.filter_by(telegram_id=field.data).first()
    #     if user and user.id != current_user.id: # If current_user is relevant, adjust
    #         raise ValidationError('This Telegram ID is already registered to another user.')