from django.db import models


class User(models.Model):
    ROLE_CHOICES   = [('delegue', 'Délégué'), ('admin', 'Admin')]
    NIVEAU_CHOICES = [('debutant', 'Débutant'), ('intermediaire', 'Intermédiaire'), ('avance', 'Avancé')]

    email          = models.EmailField(unique=True)
    password_hash  = models.CharField(max_length=255)
    first_name     = models.CharField(max_length=100)
    last_name      = models.CharField(max_length=100)
    role           = models.CharField(max_length=20, choices=ROLE_CHOICES, default='delegue')
    niveau         = models.CharField(max_length=20, choices=NIVEAU_CHOICES, default='debutant')
    current_module = models.IntegerField(default=1)
    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def calculate_niveau(self):
        """Calcule le niveau basé sur la moyenne des scores globaux."""
        assignments = self.assignments.all()
        if not assignments:
            return 'débutant'
        
        avg_score = sum(a.score_global for a in assignments) / len(assignments)
        
        if avg_score >= 85:
            return 'confirmé'
        elif avg_score >= 65:
            return 'intermédiaire'
        else:
            return 'débutant'

    def __str__(self):
        return f"{self.full_name()} ({self.role})"


class Medicament(models.Model):
    nom                    = models.CharField(max_length=255, unique=True)
    forme                  = models.CharField(max_length=100, blank=True)
    principe_actif         = models.CharField(max_length=255, blank=True)
    classe_therapeutique   = models.CharField(max_length=255, blank=True)
    indications            = models.TextField(blank=True)
    posologie              = models.TextField(blank=True)
    contre_indications     = models.TextField(blank=True)
    effets_indesirables    = models.TextField(blank=True)
    mecanisme_action       = models.TextField(blank=True)
    avantage_differentiant = models.TextField(blank=True)
    conservation           = models.CharField(max_length=255, blank=True)
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'medicaments'

    def __str__(self):
        return self.nom


class Assignment(models.Model):
    STATUT_CHOICES = [
        ('non_commence', 'Non commencé'),
        ('en_cours',     'En cours'),
        ('termine',      'Terminé'),
    ]

    delegue    = models.ForeignKey(User,       on_delete=models.CASCADE, related_name='assignments')
    medicament = models.ForeignKey(Medicament, on_delete=models.CASCADE, related_name='assignments')
    score_module1  = models.IntegerField(default=0)
    score_module2  = models.IntegerField(default=0)
    score_module3  = models.IntegerField(default=0)
    score_global   = models.IntegerField(default=0)
    statut         = models.CharField(max_length=20, choices=STATUT_CHOICES, default='non_commence')
    assigned_at    = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assignments'
        unique_together = ('delegue', 'medicament')

    def __str__(self):
        return f"{self.delegue.full_name()} → {self.medicament.nom} ({self.score_global}/100)"


class SimSession(models.Model):
    MODE_CHOICES = [('training', 'Training'), ('exam', 'Examen')]
    INTERLOCUTEUR_CHOICES = [('medecin', 'Médecin'), ('pharmacien', 'Pharmacien')]

    delegue      = models.ForeignKey(User,       on_delete=models.CASCADE, related_name='sim_sessions')
    medicament   = models.ForeignKey(Medicament, on_delete=models.CASCADE, related_name='sim_sessions')
    mode         = models.CharField(max_length=20, choices=MODE_CHOICES, default='training')
    interlocuteur = models.CharField(max_length=20, choices=INTERLOCUTEUR_CHOICES, default='medecin')

    score_contenu      = models.IntegerField(null=True, blank=True)
    score_comportement = models.IntegerField(null=True, blank=True)
    score_voix         = models.IntegerField(null=True, blank=True)
    score_final        = models.IntegerField(null=True, blank=True)

    nb_tours           = models.IntegerField(default=0)
    duree_secondes     = models.IntegerField(null=True, blank=True)
    bilan_text         = models.TextField(blank=True)
    conversation_json  = models.JSONField(default=list)
    vision_report_json = models.JSONField(default=dict)
    prosody_report_json= models.JSONField(default=dict)
    objets_detectes    = models.CharField(max_length=500, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sim_sessions'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.delegue.full_name()} | {self.medicament.nom} | {self.mode} | {self.started_at:%Y-%m-%d}"


class SessionMemory(models.Model):
    delegue       = models.ForeignKey(User,       on_delete=models.CASCADE)
    medicament    = models.ForeignKey(Medicament, on_delete=models.CASCADE)
    summary_text  = models.TextField(blank=True)
    weak_points   = models.TextField(blank=True)
    strong_points = models.TextField(blank=True)
    last_module   = models.IntegerField(default=1)
    session_date  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'session_memory'
