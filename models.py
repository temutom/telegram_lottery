# models.py
from datetime import datetime, timedelta
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta # Make sure datetime and timedelta are imported if used here

# Initialize these globally, but they will be initialized with the app
# inside the create_app() function. This avoids circular imports.
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = None # Will be initialized in app.py

# A placeholder for load_user before login_manager is fully set up
# It will be assigned properly when login_manager is initialized in app.py
def init_login_manager(lm_instance):
    global login_manager
    login_manager = lm_instance
    @login_manager.user_loader
    def load_user(user_id):
        # We need AdminUser to be defined first, so this has to be carefully ordered
        # Or you can do a deferred import if AdminUser is in this file
        return AdminUser.query.get(int(user_id))


class AdminUser(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    def __init__(self, username, password_raw):
        self.username = username
        self.password = bcrypt.generate_password_hash(password_raw).decode('utf-8')

    def verify_password(self, password_raw):
        return bcrypt.check_password_hash(self.password, password_raw)

    def __repr__(self):
        return f"AdminUser('{self.username}')"


class Draw(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    total_tickets = db.Column(db.Integer, nullable=False)
    ticket_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    draw_time = db.Column(db.DateTime, nullable=True) # When the draw is executed
    is_active = db.Column(db.Boolean, default=True) # Can users buy tickets for it?
    is_drawn = db.Column(db.Boolean, default=False) # Has the draw been executed?
    tickets = db.relationship('Ticket', backref='draw', lazy=True)
    winners = db.relationship('Winner', backref='draw', lazy=True)

    def get_status_counts(self):
        # Initialize all possible statuses to 0
        status_counts = {
            'available': 0,
            'pending_payment': 0,
            'approved': 0,
            'won': 0,
            'rejected': 0 # Ensure all possible Ticket statuses are listed here
        }
 # Query counts from the database
        # This performs a database query to get the count for each status.
        ticket_counts = db.session.query(Ticket.status, db.func.count(Ticket.id))\
                                  .filter_by(draw_id=self.id)\
                                  .group_by(Ticket.status)\
                                  .all()
                                  # Update the initialized dictionary with actual counts from the query
        for status, count in ticket_counts:
            if status in status_counts: # Only update if the status is one we're tracking
                status_counts[status] = count

        return status_counts

    # Make sure to also include the get_collected_pot method as it's used in admin_draw_details.html
    def get_collected_pot(self):
        approved_tickets_count = db.session.query(db.func.count(Ticket.id))\
                                          .filter_by(draw_id=self.id, status='approved')\
                                          .scalar()
        return approved_tickets_count * self.ticket_price if approved_tickets_count else 0.0

    # ... other methods and attributes of the Draw model ...
   # def get_collected_pot(self):
     #   from flask import current_app
     #   with current_app.app_context():
      #      approved_tickets_count = Ticket.query.filter_by(draw_id=self.id, status='approved').count()
      #      return approved_tickets_count * self.ticket_price


    def __repr__(self):
        return f"<Draw {self.name} ({self.total_tickets} tickets, ${self.ticket_price})>"

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    draw_id = db.Column(db.Integer, db.ForeignKey('draw.id'), nullable=False)
    ticket_number = db.Column(db.Integer, nullable=False) # 1 to N
    user_telegram_id = db.Column(db.BigInteger, nullable=True) # User who reserved it
    user_username = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(20), default='available', nullable=False) # available, pending_payment, approved, won
    reserved_at = db.Column(db.DateTime, nullable=True) # When reservation happened
    approved_at = db.Column(db.DateTime, nullable=True) # When admin approved payment

    __table_args__ = (db.UniqueConstraint('draw_id', 'ticket_number', name='_draw_ticket_uc'),)

    def __repr__(self):
        return f"<Ticket {self.draw.name} #{self.ticket_number} - Status: {self.status}>"

class Winner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    draw_id = db.Column(db.Integer, db.ForeignKey('draw.id'), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    place = db.Column(db.Integer, nullable=False)  # 1st, 2nd, 3rd
    prize_amount = db.Column(db.Float, nullable=False)
    won_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    ticket = db.relationship('Ticket', backref='winner_entry', uselist=False)

    def __repr__(self):
        return f"<Winner Draw {self.draw_id} - {self.place} Place - Ticket #{self.ticket.ticket_number}>"
