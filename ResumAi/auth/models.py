# ResumAi/auth/models.py (new file)
from flask_login import UserMixin
from ..models import User as BaseUser

class AuthUser(UserMixin, BaseUser):
    pass

# In ResumAi/models.py - REMOVE UserMixin and @login_manager.user_loader decorator

# In ResumAi/__init__.py - ADD after login_manager.init_app(app):
from .auth.models import AuthUser
@login_manager.user_loader
def load_user(user_id):
    return AuthUser.query.get(int(user_id))
