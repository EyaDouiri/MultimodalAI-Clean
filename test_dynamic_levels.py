#!/usr/bin/env python3
"""
Test script for dynamic level calculation
Verify that calculate_niveau() works correctly
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, r'c:\Users\eyaen\Desktop\PI\alia_backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alia_backend.settings')
django.setup()

from api.models import User, Assignment, Medicament

def test_level_calculation():
    """Test the calculate_niveau() method"""
    
    print("\n" + "="*60)
    print("Testing Dynamic Level Calculation")
    print("="*60 + "\n")
    
    # Get a test delegue (create if needed)
    user, created = User.objects.get_or_create(
        email='test_niveau@example.com',
        defaults={
            'first_name': 'Test',
            'last_name': 'Niveau',
            'role': 'delegue',
            'is_active': True,
            'password_hash': 'test_hash'
        }
    )
    
    print(f"Test User: {user.full_name()} ({user.email})")
    print(f"Created: {created}\n")
    
    # Get a test medicament
    med = Medicament.objects.first()
    if not med:
        print("❌ No medicaments found. Please load medicaments first.")
        return
    
    print(f"Using medicament: {med.nom}\n")
    
    # Test 1: No assignments (should be débutant)
    print("Test 1: No assignments")
    print(f"  Expected: débutant")
    print(f"  Actual: {user.calculate_niveau()}")
    assert user.calculate_niveau() == 'débutant', "Failed: No assignments should be débutant"
    print("  ✓ Passed\n")
    
    # Test 2: Average score < 65 (should be débutant)
    print("Test 2: Average score < 65 (scores: 50, 60, 70)")
    Assignment.objects.filter(delegue=user).delete()
    for i, score in enumerate([50, 60, 70]):
        med_test, _ = Medicament.objects.get_or_create(
            nom=f'test_med_{i}',
            defaults={'forme': 'tablet'}
        )
        Assignment.objects.create(
            delegue=user,
            medicament=med_test,
            score_module1=score,
            score_module2=score,
            score_module3=score
        )
    
    user.refresh_from_db()  # Refresh to get updated assignments
    avg = sum(a.score_global for a in user.assignments.all()) / user.assignments.count()
    niveau = user.calculate_niveau()
    print(f"  Average score: {avg:.1f}")
    print(f"  Expected: débutant")
    print(f"  Actual: {niveau}")
    assert niveau == 'débutant', "Failed: Average < 65 should be débutant"
    print("  ✓ Passed\n")
    
    # Test 3: Average score 65-85 (should be intermédiaire)
    print("Test 3: Average score 65-85 (scores: 70, 80, 90)")
    Assignment.objects.filter(delegue=user).delete()
    for i, score in enumerate([70, 80, 90]):
        med_test, _ = Medicament.objects.get_or_create(
            nom=f'test_med_inter_{i}',
            defaults={'forme': 'tablet'}
        )
        Assignment.objects.create(
            delegue=user,
            medicament=med_test,
            score_module1=score,
            score_module2=score,
            score_module3=score
        )
    
    user.refresh_from_db()
    avg = sum(a.score_global for a in user.assignments.all()) / user.assignments.count()
    niveau = user.calculate_niveau()
    print(f"  Average score: {avg:.1f}")
    print(f"  Expected: intermédiaire")
    print(f"  Actual: {niveau}")
    assert niveau == 'intermédiaire', "Failed: Average 65-85 should be intermédiaire"
    print("  ✓ Passed\n")
    
    # Test 4: Average score >= 85 (should be confirmé)
    print("Test 4: Average score >= 85 (scores: 85, 90, 95)")
    Assignment.objects.filter(delegue=user).delete()
    for i, score in enumerate([85, 90, 95]):
        med_test, _ = Medicament.objects.get_or_create(
            nom=f'test_med_conf_{i}',
            defaults={'forme': 'tablet'}
        )
        Assignment.objects.create(
            delegue=user,
            medicament=med_test,
            score_module1=score,
            score_module2=score,
            score_module3=score
        )
    
    user.refresh_from_db()
    avg = sum(a.score_global for a in user.assignments.all()) / user.assignments.count()
    niveau = user.calculate_niveau()
    print(f"  Average score: {avg:.1f}")
    print(f"  Expected: confirmé")
    print(f"  Actual: {niveau}")
    assert niveau == 'confirmé', "Failed: Average >= 85 should be confirmé"
    print("  ✓ Passed\n")
    
    print("="*60)
    print("✓ All tests passed!")
    print("="*60 + "\n")
    
    # Cleanup
    Assignment.objects.filter(delegue=user).delete()
    user.delete()
    Medicament.objects.filter(nom__startswith='test_med').delete()

if __name__ == '__main__':
    test_level_calculation()
