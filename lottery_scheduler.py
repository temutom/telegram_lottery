# lottery_scheduler.py
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Ensure environment variables are loaded for this script too
load_dotenv()

# We need to create a dummy app context to use Flask-SQLAlchemy outside the main app.
# Import create_app from app.py
from app import create_app, db, Ticket, application # Import application as well for bot messaging

# Create a minimal app instance for the scheduler to use
# This app won't run a web server, but provides the app context for DB operations
scheduler_app = create_app()

async def clean_expired_tickets_task():
    """
    Reverts 'pending_payment' tickets to 'available' after their reservation expires.
    This task is designed to be run by a background scheduler (e.g., Render Cron Job).
    """
    print("Running expired ticket cleaner...")
    with scheduler_app.app_context():
        expiry_threshold = datetime.utcnow() - timedelta(hours=scheduler_app.config['TICKET_RESERVATION_EXPIRY_HOURS'])

        expired_tickets = Ticket.query.filter(
            Ticket.status == 'pending_payment',
            Ticket.reserved_at < expiry_threshold
        ).all()

        for ticket in expired_tickets:
            print(f"Reverting expired ticket #{ticket.ticket_number} for Draw '{ticket.draw.name}' (User: {ticket.user_telegram_id})")
            ticket.status = 'available'
            ticket.user_telegram_id = None
            ticket.user_username = None
            ticket.reserved_at = None
            db.session.add(ticket)

            # Optional: Notify user that reservation expired via Telegram Bot
            if ticket.user_telegram_id:
                try:
                    # 'application' is the global bot instance initialized in create_app()
                    await application.bot.send_message(
                        chat_id=ticket.user_telegram_id,
                        text=f"⏰ Your reservation for Ticket #{ticket.ticket_number} in Draw '{ticket.draw.name}' has expired "
                             "due to non-payment. The ticket is now available again."
                    )
                except Exception as e:
                    print(f"Failed to send expiry message to {ticket.user_telegram_id}: {e}")

        db.session.commit()
        print(f"Cleaned {len(expired_tickets)} expired tickets.")

if __name__ == '__main__':
    # When this script is run, execute the cleaning task
    asyncio.run(clean_expired_tickets_task())