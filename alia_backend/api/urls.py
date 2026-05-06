from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('auth/login',              views.login,              name='login'),

    # Délégué
    path('delegue/profil',          views.delegue_profil,     name='delegue_profil'),
    path('delegue/historique',      views.delegue_historique, name='delegue_historique'),

    # Médicaments (accessible à tous les users authentifiés)
    path('medicaments',             views.medicaments_list,   name='medicaments_list'),

    # Simulation
    path('sim/start',               views.sim_start,          name='sim_start'),
    path('sim/message',             views.sim_message,        name='sim_message'),
    path('sim/stop',                views.sim_stop,           name='sim_stop'),
    path('sim/command',             views.sim_command,        name='sim_command'),

    # Avatar state (utilisé par agent.py + alia_avatar.html)
    path('avatar/state',            views.avatar_state_push,  name='avatar_state_push'),
    path('avatar/last',             views.avatar_state_get,   name='avatar_state_get'),

    # Admin
    path('admin/delegues',          views.admin_delegues,     name='admin_delegues'),
    path('admin/assignments',       views.admin_assignments,  name='admin_assignments'),
    path('admin/assign',            views.admin_assign,       name='admin_assign'),
    path('admin/assignment/<int:assignment_id>', views.admin_assignment_detail, name='admin_assignment_detail'),
    path('admin/medicaments',       views.admin_medicaments,  name='admin_medicaments'),
    path('admin/create-user',       views.admin_create_user,  name='admin_create_user'),
]
