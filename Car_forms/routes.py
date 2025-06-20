from flask import render_template, url_for, flash, redirect, request
from Car_forms import app, db, bcrypt
from Car_forms.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, CommentForm, ReplyForm
from Car_forms.models import User, Post,Comment
from flask_login import login_user, current_user, logout_user, login_required
from PIL import Image
import os
import secrets

from flask import request, redirect, url_for, flash

@app.route("/", methods=["GET", "POST"])
def home():
    comment_form = CommentForm()
    reply_form = ReplyForm()

    if request.method == "POST":
        if "comment_submit" in request.form and comment_form.validate_on_submit():
            # New top-level comment
            content = comment_form.content.data
            new_comment = Comment(content=content, user_id=current_user.id, post_id=int(request.form.get("post_id")), parent_id=None)
            db.session.add(new_comment)
            db.session.commit()
            flash("Comment posted!", "success")
            return redirect(url_for("home"))

        if "reply_submit" in request.form and reply_form.validate_on_submit():
            # Reply to a comment
            content = reply_form.content.data
            post_id = int(request.form.get("post_id"))
            parent_id_raw = request.form.get("parent_id")
            parent_id = int(parent_id_raw) if parent_id_raw else None

            new_reply = Comment(content=content, user_id=current_user.id, post_id=post_id, parent_id=parent_id)
            db.session.add(new_reply)
            db.session.commit()
            flash("Reply posted!", "success")
            return redirect(url_for("home"))

    posts = Post.query.order_by(Post.date_posted.desc()).all()
    # Prepare top-level comments and replies for template as explained before
    for post in posts:
        post.top_level_comments = [c for c in post.comments if c.parent_id is None]
        for comment in post.top_level_comments:
            comment.sorted_replies = comment.replies.order_by(Comment.date_posted).all()

    return render_template("home.html", posts=posts, comment_form=comment_form, reply_form=reply_form)



@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/sign_up", methods=['GET', 'POST'])
def sign_up():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in!', 'success')
        return redirect(url_for('login'))
    else:
        if form.errors:
            flash('Please correct the errors in the form.', 'danger')
    return render_template('sign_up.html', title='Sign Up', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


def save_post_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/post_pics', picture_fn)

    output_size = (800, 800)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        if form.username.data == current_user.username and form.email.data == current_user.email and not form.picture.data:
            flash('No changes made to your account.', 'info')
            return redirect(url_for('account'))
        else:
            db.session.commit()
            flash('Your account has been updated!', 'success')
            return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account', image_file=image_file, form=form)


@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_post_picture(form.picture.data)
            post = Post(title=form.title.data, content=form.content.data, author=current_user, image_file=picture_file)
        else:
            post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('create_post'))

    posts = Post.query.filter_by(author=current_user).order_by(Post.date_posted.desc()).all()
    return render_template('create_post.html', form=form, posts=posts)


@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash('You are not authorized to edit this post.', 'danger')
        return redirect(url_for('home'))

    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        if form.picture.data:
            picture_file = save_post_picture(form.picture.data)
            post.image_file = picture_file
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('create_post'))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content

    return render_template('create_post.html', form=form, post=post)


@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        flash('You are not authorized to delete this post.', 'danger')
        return redirect(url_for('home'))

    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))