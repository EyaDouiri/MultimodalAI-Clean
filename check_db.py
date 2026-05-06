#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alia_backend.settings')
sys.path.insert(0, 'c:\\Users\\eyaen\\Desktop\\PI\\alia_backend')
django.setup()

from api.models import User, Medicament, Assignment, SimSession

print("=" * 60)
print("📊 DATABASE INVENTORY")
print("=" * 60)

# Check Users
print("\n👥 USERS:")
users = User.objects.all()
for user in users:
    print(f"  - {user.email} ({user.role}) - {user.first_name} {user.last_name}")
print(f"   Total: {users.count()}")

# Check Medicaments
print("\n💊 MEDICAMENTS:")
meds = Medicament.objects.all()
for med in meds:
    print(f"  - {med.nom}")
print(f"   Total: {meds.count()}")

# Check Assignments
print("\n📋 ASSIGNMENTS:")
assignments = Assignment.objects.all()
for assign in assignments:
    print(f"  - {assign.delegue.email} → {assign.medicament.nom} (Score: {assign.score_global}, Status: {assign.statut})")
print(f"   Total: {assignments.count()}")

# Check Sessions
print("\n🎬 SIMULATION SESSIONS:")
sessions = SimSession.objects.all()
print(f"   Total: {sessions.count()}")
if sessions.count() > 0:
    for sess in sessions[:3]:
        print(f"  - Session {sess.id}: {sess.delegue.email} → {sess.medicament.nom}")

print("\n" + "=" * 60)
print("✅ Database ready for testing!")
print("=" * 60)
