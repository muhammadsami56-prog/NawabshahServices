
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from config import Config
from models import db, User, Service, ServiceRequest

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login first.'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()


@app.route('/')
def home():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()

    query = Service.query

    if search:
        query = query.filter(
            db.or_(
                Service.title.ilike(f'%{search}%'),
                Service.description.ilike(f'%{search}%')
            )
        )

    if category:
        query = query.filter_by(category=category)

    services = query.order_by(Service.created_at.desc()).all()

    return render_template(
        'home.html',
        services=services,
        search=search,
        selected_category=category
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'customer')

        if not name or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('register'))

        if role not in ['customer', 'provider']:
            flash('Invalid account type.', 'danger')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'danger')
            return redirect(url_for('register'))

        user = User(name=name, email=email, phone=phone, role=role)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/add-service', methods=['GET', 'POST'])
@login_required
def add_service():
    if current_user.role != 'provider':
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        price_input = request.form.get('price', '').strip()

        if not all([title, description, category, price_input]):
            flash('Please fill in all fields.', 'danger')
            return redirect(url_for('add_service'))

        try:
            price = float(price_input)
            if price < 0 or price != price or price == float('inf'):
                raise ValueError
        except ValueError:
            flash('Please enter a valid price.', 'danger')
            return redirect(url_for('add_service'))

        service = Service(
            title=title,
            description=description,
            category=category,
            price=price,
            provider_id=current_user.id
        )

        db.session.add(service)
        db.session.commit()

        flash('Service posted successfully!', 'success')
        return redirect(url_for('my_services'))

    return render_template('add_service.html')


@app.route('/my-services')
@login_required
def my_services():
    if current_user.role != 'provider':
        abort(403)

    services = Service.query.filter_by(
        provider_id=current_user.id
    ).order_by(Service.created_at.desc()).all()

    return render_template('my_services.html', services=services)


@app.route('/delete-service/<int:id>', methods=['POST'])
@login_required
def delete_service(id):
    if current_user.role != 'provider':
        abort(403)

    service = Service.query.get_or_404(id)

    if service.provider_id != current_user.id:
        abort(403)

    ServiceRequest.query.filter_by(service_id=service.id).delete()

    db.session.delete(service)
    db.session.commit()

    flash('Service deleted successfully!', 'success')
    return redirect(url_for('my_services'))


@app.route('/service/<int:id>')
def service_detail(id):
    service = Service.query.get_or_404(id)
    return render_template('service_detail.html', service=service)


@app.route('/request-service/<int:id>', methods=['POST'])
@login_required
def request_service(id):
    if current_user.role != 'customer':
        abort(403)

    service = Service.query.get_or_404(id)

    if service.provider_id == current_user.id:
        abort(403)

    message = request.form.get('message', '').strip()

    new_request = ServiceRequest(
        service_id=service.id,
        customer_id=current_user.id,
        message=message
    )

    db.session.add(new_request)
    db.session.commit()

    flash('Your service request has been submitted!', 'success')
    return redirect(url_for('my_requests'))


@app.route('/my-requests')
@login_required
def my_requests():
    if current_user.role != 'customer':
        abort(403)

    requests = ServiceRequest.query.filter_by(
        customer_id=current_user.id
    ).order_by(ServiceRequest.created_at.desc()).all()

    return render_template('my_requests.html', requests=requests)


@app.route('/service-requests')
@login_required
def provider_requests():
    if current_user.role != 'provider':
        abort(403)

    requests = (
        ServiceRequest.query
        .join(Service, ServiceRequest.service_id == Service.id)
        .filter(Service.provider_id == current_user.id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )

    return render_template('provider_requests.html', requests=requests)


@app.route('/update-request/<int:id>/<status>', methods=['POST'])
@login_required
def update_request(id, status):
    if current_user.role != 'provider':
        abort(403)

    if status not in ['Accepted', 'Rejected']:
        abort(400)

    service_request = ServiceRequest.query.get_or_404(id)

    if service_request.service.provider_id != current_user.id:
        abort(403)

    service_request.status = status
    db.session.commit()

    flash(f'Request {status.lower()} successfully.', 'success')
    return redirect(url_for('provider_requests'))


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have logged out successfully.', 'success')
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
