from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, InventoryItem , Category
from flask import send_file
import pandas as pd

routes = Blueprint('routes', __name__)

# Authentication Routes
@routes.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('routes.register'))
            
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('routes.login'))
    return render_template('register.html')

@routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('routes.dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@routes.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('routes.login'))


@routes.route('/add', methods=['GET', 'POST'])
@login_required
def add_item():
    categories = Category.query.all()
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        quantity = request.form['quantity']
        
        new_item = InventoryItem(
            name=name,
            description=description,
            quantity=quantity,
            user_id=current_user.id,
            category_id=request.form.get('category')
        )
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for('routes.dashboard'))
    return render_template('add_item.html', categories=categories)

@routes.route('/delete/<int:id>')
@login_required
def delete_item(id):
    item = InventoryItem.query.get_or_404(id)
    if item.owner != current_user:
        abort(403)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('routes.dashboard'))

@routes.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_item(id):
    categories = Category.query.all()
    item = InventoryItem.query.get_or_404(id)
    
    if item.owner != current_user:
        abort(403)
        
    if request.method == 'POST':
        item.name = request.form['name']
        item.description = request.form['description']
        item.quantity = request.form['quantity']
        item.category_id = request.form.get('category')
        db.session.commit()
        return redirect(url_for('routes.dashboard'))
    return render_template('edit_item.html', item=item , categories=categories)


@routes.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 5  # Match dashboard pagination
    
    # Get base query
    search_query = InventoryItem.query.filter(
        InventoryItem.name.ilike(f'%{query}%'),
        InventoryItem.user_id == current_user.id
    )
    
    # Paginate results
    items = search_query.paginate(page=page, per_page=per_page, error_out=False)
    categories = Category.query.all()
    
    return render_template('dashboard.html', items=items, categories=categories, selected_category=None, search_query=query)


@routes.route('/dashboard')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    selected_categories = request.args.getlist('categories', type=int)
    search_query = request.args.get('q', '')
    per_page = 5

    # Base query
    query = InventoryItem.query.filter_by(user_id=current_user.id)

    # Apply category filter
    if selected_categories:
        query = query.filter(InventoryItem.category_id.in_(selected_categories))

    # Apply search filter
    if search_query:
        query = query.filter(InventoryItem.name.ilike(f'%{search_query}%'))

    # Paginate results
    items = query.paginate(page=page, per_page=per_page, error_out=False)
    
    categories = Category.query.all()
    
    return render_template('dashboard.html',
                        items=items,
                        categories=categories,
                        selected_categories=selected_categories,
                        search_query=search_query)


@routes.route('/export')
@login_required
def export_items():
    items = InventoryItem.query.filter_by(user_id=current_user.id).all()

    # Create DataFrame with category information
    data = []
    for item in items:
        data.append({
            'Name': item.name,
            'Description': item.description,
            'Quantity': item.quantity,
            'Category': item.item_category.name if item.item_category else ''
        })
    
    df = pd.DataFrame(data)
    df.to_excel('inventory.xlsx', index=False)
    return send_file('inventory.xlsx', as_attachment=True)


@routes.route('/import', methods=['POST'])
@login_required
def import_items():
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('routes.dashboard'))
    
    file = request.files['file']
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            flash('Unsupported file format')
            return redirect(url_for('routes.dashboard'))

        # Add items to database with categories
        for _, row in df.iterrows():
            category_name = row.get('Category', '')
            category = Category.query.filter_by(name=category_name).first() if category_name else None

            item = InventoryItem(
                name=row['Name'],
                description=row.get('Description', ''),
                quantity=row['Quantity'],
                user_id=current_user.id,
                category_id=category.id if category else None
            )
            db.session.add(item)
            
        db.session.commit()
        flash('Items imported successfully')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing items: {str(e)}')
    
    return redirect(url_for('routes.dashboard'))


@routes.route('/categories')
@login_required
def manage_categories():
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)


@routes.route('/home')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('routes.dashboard'))
    return render_template('index.html')


# Update existing routes to use index as landing
@routes.route('/')
def home_redirect():
    return redirect(url_for('routes.index'))


@routes.route('/category/add', methods=['POST'])
@login_required
def add_category():
    name = request.form['name']
    new_category = Category(name=name)
    db.session.add(new_category)
    db.session.commit()
    return redirect(url_for('routes.manage_categories'))


@routes.route('/category/delete/<int:id>')
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('routes.manage_categories'))