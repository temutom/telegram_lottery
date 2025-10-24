import os
import random
import asyncio
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Blueprint, current_app
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from flask_wtf.csrf import generate_csrf

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from models import db, bcrypt, AdminUser, Draw, Ticket, Winner, init_login_manager
from forms import AdminLoginForm, CreateDrawForm, CSRFOnlyForm
import config

# Load environment variables
load_dotenv()

# Global Telegram bot application
#application = None
# Global Telegram bot
telegram_app = None
# ---------------- Telegram Handlers ----------------
# ---------------- Telegram Bot Commands ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Detect environment for correct web app URL
    web_app_url = os.getenv("https://telegram-lottery.onrender.com", "http://127.0.0.1:5000")
    await update.message.reply_text(
        f"🎟️እንኳን ወደ ፈጣን ሎተሪ በደህና መጡ!\n"
        f"የጨዋታ ቁጥር ለመምረጥ ይህንን ዌብሳይት ይጎብኙ!!\n"
        f"🎟️ Welcome to the Lottery Bot!\n"
        f"Visit the web app to reserve tickets:\n{web_app_url}\n\n"
        f"Your Telegram ID: `{update.effective_user.id}`",
        parse_mode="Markdown"
    )

async def my_tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_telegram_id = str(update.effective_user.id)
    with current_app.app_context():
        tickets = Ticket.query.filter_by(user_telegram_id=user_telegram_id).order_by(Ticket.reserved_at.desc()).all()
        if not tickets:
            await update.message.reply_text("You have no tickets reserved or approved yet.")
            return
        response_text = "🎟️ *Your Tickets:*\n"
        for ticket in tickets:
            draw_name = ticket.draw.name
            status_emoji = {
                "pending_payment": "⏳",
                "approved": "✅",
                "available": "🎫"
            }.get(ticket.status, "❔")
            response_text += f"{status_emoji} *Draw:* {draw_name}, Ticket #{ticket.ticket_number} (*{ticket.status}*)\n"
            if ticket.status == 'pending_payment' and ticket.reserved_at:
                expiry_time = ticket.reserved_at + timedelta(
                    hours=current_app.config.get('TICKET_RESERVATION_EXPIRY_HOURS', 24)
                )
                response_text += f"   ⏰ Expires: {expiry_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        await update.message.reply_text(response_text, parse_mode="Markdown")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Use /start or /my_tickets.")


def setup_telegram_bot():
    global telegram_app
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN not set in .env")
        return None
    telegram_app = Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("my_tickets", my_tickets_command))
    telegram_app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    return telegram_app


# ---------------- Admin Blueprint ----------------
admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates/admin')

@admin_bp.route('/')
@login_required
def dashboard():
    draws = Draw.query.order_by(Draw.created_at.desc()).all()
    return render_template('admin_dashboard.html', draws=draws)

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    form = AdminLoginForm()
    if form.validate_on_submit():
        user = AdminUser.query.filter_by(username=form.username.data).first()
        if user and user.verify_password(form.password.data):
            login_user(user)
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('admin_login.html', form=form)

@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('admin.login'))

@admin_bp.route('/create_draw', methods=['GET', 'POST'])
@login_required
def create_draw():
    form = CreateDrawForm()
    if form.validate_on_submit():
        new_draw = Draw(
            name=form.name.data,
            total_tickets=form.total_tickets.data,
            ticket_price=form.ticket_price.data
        )
        db.session.add(new_draw)
        db.session.commit()

        # Create tickets for this draw
        for i in range(1, new_draw.total_tickets + 1):
            ticket = Ticket(draw_id=new_draw.id, ticket_number=i, status='available')
            db.session.add(ticket)
        db.session.commit()

        flash(f'Draw "{new_draw.name}" created successfully with {new_draw.total_tickets} tickets!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin_create_draw.html', form=form)

@admin_bp.route('/draw_details/<int:draw_id>')
@login_required
def draw_details(draw_id):
    draw = Draw.query.get_or_404(draw_id)
    all_tickets = Ticket.query.filter_by(draw_id=draw.id).order_by(Ticket.ticket_number).all()
    winners = Winner.query.filter_by(draw_id=draw.id).order_by(Winner.place).all()
    csrf_form = CSRFOnlyForm()
    return render_template('admin_draw_details.html', draw=draw, tickets=all_tickets, winners=winners, csrf_form=csrf_form)

@admin_bp.route('/approve_payment/<int:ticket_id>', methods=['POST'])
@login_required
def approve_payment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.status == 'pending_payment':
        ticket.status = 'approved'
        ticket.approved_at = datetime.utcnow()
        db.session.commit()
        flash(f'Ticket #{ticket.ticket_number} approved.', 'success')
    else:
        flash('Ticket is not in pending status.', 'warning')
    return redirect(url_for('admin.draw_details', draw_id=ticket.draw_id))

@admin_bp.route('/reject_payment/<int:ticket_id>', methods=['POST'])
@login_required
def reject_payment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.status == 'pending_payment':
        ticket.status = 'available'
        ticket.user_telegram_id = None
        ticket.user_username = None
        ticket.reserved_at = None
        db.session.commit()
        flash(f'Ticket #{ticket.ticket_number} reverted to available.', 'info')
    else:
        flash('Ticket is not in pending status.', 'warning')
    return redirect(url_for('admin.draw_details', draw_id=ticket.draw_id))

@admin_bp.route('/draw_execute/<int:draw_id>', methods=['POST'])
@login_required
def draw_execute(draw_id):
    draw = Draw.query.get_or_404(draw_id)
    if draw.is_drawn:
        flash('Draw already executed!', 'info')
        return redirect(url_for('admin.draw_details', draw_id=draw.id))

    approved_tickets = Ticket.query.filter_by(draw_id=draw.id, status='approved').all()
    if len(approved_tickets) < 1:
        flash('No approved tickets to draw winners!', 'danger')
        return redirect(url_for('admin.draw_details', draw_id=draw.id))

    total_prize_pool = draw.ticket_price * len(approved_tickets)
    prize_distribution = [0.4, 0.2, 0.1]  # 40%, 20%, 10%
    num_winners = min(3, len(approved_tickets))
    selected_winners = random.sample(approved_tickets, num_winners)

    for idx, ticket in enumerate(selected_winners, start=1):
        prize_amount = round(total_prize_pool * prize_distribution[idx - 1], 2)
        winner = Winner(
            place=idx,
            prize_amount=prize_amount,
            ticket_id=ticket.id,
            draw_id=draw.id,
            won_at=datetime.utcnow()
        )
        db.session.add(winner)

        # Telegram notification
        if ticket.user_telegram_id and application:
            try:
                message = (
                    f"🎉 Congratulations! You won ${prize_amount:.2f} in the draw '{draw.name}'!\n"
                    f"Your ticket: #{ticket.ticket_number}\n"
                    f"Place: {idx}{ordinal_suffix(idx)}"
                )
                asyncio.run_coroutine_threadsafe(
                    application.bot.send_message(chat_id=int(ticket.user_telegram_id), text=message),
                    asyncio.get_event_loop()
                )
            except Exception as e:
                print(f"Failed to send Telegram message to {ticket.user_telegram_id}: {e}")

    draw.is_drawn = True
    db.session.commit()
    flash('🎉 Draw executed successfully! Winners selected.', 'success')
    return redirect(url_for('admin.draw_details', draw_id=draw.id))


@admin_bp.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
@login_required
def delete_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    draw_id = ticket.draw_id
    db.session.delete(ticket)
    db.session.commit()
    flash(f'Ticket #{ticket.ticket_number} deleted successfully.', 'info')
    return redirect(url_for('admin.draw_details', draw_id=draw_id))
@admin_bp.route('/delete_winner/<int:winner_id>', methods=['POST'])
@login_required
def delete_winner(winner_id):
    winner = Winner.query.get_or_404(winner_id)
    draw_id = winner.draw_id
    try:
        db.session.delete(winner)
        db.session.commit()
        flash(f'Winner for ticket #{winner.ticket.ticket_number} deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting winner: {e}', 'danger')
    return redirect(url_for('admin.draw_details', draw_id=draw_id))
@admin_bp.route('/reset_draw/<int:draw_id>', methods=['POST'])
@login_required
def reset_draw(draw_id):
    draw = Draw.query.get_or_404(draw_id)
    try:
        # Delete winners first
        Winner.query.filter_by(draw_id=draw.id).delete(synchronize_session=False)
        # Delete tickets
        Ticket.query.filter_by(draw_id=draw.id).delete(synchronize_session=False)
        draw.is_drawn = False
        draw.draw_time = None
        db.session.commit()
        flash(f'✅ Draw "{draw.name}" has been reset. All tickets and winners deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting draw: {e}', 'danger')
    return redirect(url_for('admin.draw_details', draw_id=draw.id))
@admin_bp.route('/delete_draw/<int:draw_id>', methods=['POST'])
@login_required
def delete_draw(draw_id):
    draw = Draw.query.get_or_404(draw_id)
    try:
        # Delete winners
        Winner.query.filter_by(draw_id=draw.id).delete(synchronize_session=False)
        # Delete tickets
        Ticket.query.filter_by(draw_id=draw.id).delete(synchronize_session=False)
        # Delete the draw itself
        db.session.delete(draw)
        db.session.commit()
        flash(f'✅ Draw "{draw.name}" and all related tickets/winners have been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting draw: {e}', 'danger')
    return redirect(url_for('admin.dashboard'))

   

# ---------------- Public Blueprint ----------------
public_bp = Blueprint('public', __name__, template_folder='templates/public')

@public_bp.route('/')
def home():
    active_draws = Draw.query.filter_by(is_active=True, is_drawn=False).order_by(Draw.created_at.desc()).all()
    drawn_draws = Draw.query.filter_by(is_drawn=True).order_by(Draw.created_at.desc()).all()
    return render_template('home.html', draws=active_draws, drawn_draws=drawn_draws)

@public_bp.route('/draw/<int:draw_id>', methods=['GET', 'POST'])
def draw_public_details(draw_id):
    draw = Draw.query.get_or_404(draw_id)
    if request.method == 'POST':
        ticket_number = request.form.get('ticket_number')
        user_telegram_id = request.form.get('user_telegram_id')
        user_username = request.form.get('user_username')

        if not (ticket_number and user_telegram_id and user_username):
            flash("All fields required.", "warning")
            return redirect(url_for('public.draw_public_details', draw_id=draw.id))

        ticket = Ticket.query.filter_by(draw_id=draw.id, ticket_number=ticket_number, status='available').first()
        if ticket:
            ticket.status = 'pending_payment'
            ticket.user_telegram_id = user_telegram_id
            ticket.user_username = user_username
            ticket.reserved_at = datetime.utcnow()
            db.session.commit()
            flash(f"Ticket #{ticket_number} ስለመረጡ እናመሰግናለን፣እባክዎ ክፍያ በ ቴሌብር 0929467615(Temesgen) ገቢ ካደረጉ በኃላ Screenshot ይላኩልን.", "success")
        else:
            flash("Ticket unavailable.", "danger")

    tickets = Ticket.query.filter_by(draw_id=draw.id).order_by(Ticket.ticket_number).all()
    winners = Winner.query.filter_by(draw_id=draw.id).order_by(Winner.place).all()
    return render_template('draw_public_details.html', draw=draw, tickets=tickets, winners=winners)

@public_bp.route('/winners')
def public_winners():
    draws_with_winners = Draw.query.filter_by(is_drawn=True).order_by(Draw.draw_time.desc()).limit(10).all()
    return render_template('public_winners.html', draws=draws_with_winners)


# ---------------- Flask App Factory ----------------
def ordinal_suffix(value):
    try:
        num = int(value)
        if 10 <= num % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(num % 10, 'th')
        return f"{num}{suffix}"
    except Exception:
        return value

def create_app():
    global application
    app = Flask(__name__)
    app.config.from_object(config.Config)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = 'admin.login'
    login_manager.login_message_category = 'info'
    init_login_manager(login_manager)

    # Telegram bot
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if TOKEN:
        from telegram.ext import Application
        application = Application.builder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("my_tickets", my_tickets_command))
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    # Global Jinja filters
    app.jinja_env.filters['ordinal'] = ordinal_suffix

    @app.context_processor
    def inject_global_vars():
        return dict(datetime=datetime, timedelta=timedelta, csrf_token=generate_csrf, config=app.config)

    return app


# ---------------- Run App ----------------
# ---------------- Create and Run ----------------
app = create_app()  # ✅ Required for Render (Gunicorn looks for this)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        setup_telegram_bot()
        if not AdminUser.query.filter_by(username="admin").first():
            default_pass = app.config.get('ADMIN_PASSWORD', 'admin123')
            admin_user = AdminUser(username="admin", password_raw=default_pass)
            db.session.add(admin_user)
            db.session.commit()
            print(f"✅ Default admin created: username=admin password={default_pass}")

    if telegram_app:
        threading.Thread(target=lambda: asyncio.run(telegram_app.run_polling())).start()

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))