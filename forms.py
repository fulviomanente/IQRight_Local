from flask_wtf import FlaskForm, RecaptchaField
from wtforms import BooleanField, StringField, TextAreaField, PasswordField, FloatField, IntegerField, HiddenField, SelectField
from wtforms.validators import InputRequired, Email
from flask_babel import lazy_gettext as _


class LoginForm(FlaskForm):
    username = StringField(_('Username'), validators=[InputRequired()])
    password = PasswordField(_('Password'), validators=[InputRequired()])

class ResetPasswordForm(FlaskForm):
    username = StringField(_('Username'), validators=[InputRequired()])

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(_('Current Password'), validators=[InputRequired()])
    new_password = PasswordField(_('New Password'), validators=[InputRequired()])
    confirm_password = PasswordField(_('Confirm Password'), validators=[InputRequired()])
    def validate(self):
        initial_validation = super(ChangePasswordForm, self).validate()
        if not initial_validation:
            return False
        if self.new_password.data != self.confirm_password.data:
            self.confirm_password.errors.append(_("Passwords do not match"))
            return False
        return True
