"""
Script om DATABASE_URL veilig toe te voegen aan .env bestand.
Controleert eerst of .env in .gitignore staat.
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
env_file = project_root / ".env"
gitignore_file = project_root / ".gitignore"


def check_gitignore():
    """Controleer of .env in .gitignore staat"""
    if not gitignore_file.exists():
        print("⚠️  .gitignore bestaat niet!")
        return False
    
    with open(gitignore_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check voor .env regel (mogelijk met .env.*)
    if '.env' in content and ('.env\n' in content or '.env\r\n' in content or '.env ' in content):
        print("✅ .env staat in .gitignore (veilig)")
        return True
    else:
        print("❌ .env staat NIET in .gitignore (ONVEILIG!)")
        print("   Voeg '.env' toe aan .gitignore voordat je doorgaat!")
        return False


def check_existing_database_url():
    """Controleer of DATABASE_URL al bestaat"""
    if not env_file.exists():
        return None
    
    with open(env_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if line.strip().startswith('DATABASE_URL='):
            return i, line.strip()
    
    return None


def add_database_url(database_url=None):
    """Voeg DATABASE_URL toe aan .env"""
    if not check_gitignore():
        print("\n❌ Stop: .env moet eerst in .gitignore staan!")
        sys.exit(1)
    
    # Check of al bestaat
    existing = check_existing_database_url()
    if existing:
        line_num, line_content = existing
        print(f"\n⚠️  DATABASE_URL bestaat al op regel {line_num + 1}:")
        print(f"   {line_content}")
        
        if database_url:
            # Non-interactief: overschrijf automatisch
            print("   Overschrijven met nieuwe waarde...")
        else:
            response = input("\nWil je deze overschrijven? (ja/nee): ").strip().lower()
            if response != 'ja':
                print("Geannuleerd.")
                return
    
    # Haal DATABASE_URL op
    if not database_url:
        # Probeer eerst environment variable
        database_url = os.getenv('DATABASE_URL_INPUT')
        
        if not database_url:
            print("\n" + "="*80)
            print("DATABASE_URL Toevoegen")
            print("="*80)
            print("\nVoer je Railway PostgreSQL DATABASE_URL in.")
            print("Format: postgresql://user:password@host:port/database")
            print("\nJe kunt deze vinden in Railway dashboard:")
            print("  - Ga naar je PostgreSQL service")
            print("  - Klik op 'Variables' of 'Connect'")
            print("  - Kopieer de DATABASE_URL")
            print()
            
            database_url = input("DATABASE_URL: ").strip()
    
    if not database_url:
        print("❌ Geen DATABASE_URL ingevoerd. Geannuleerd.")
        sys.exit(1)
    
    if not database_url.startswith('postgresql://'):
        print("⚠️  Waarschuwing: DATABASE_URL begint niet met 'postgresql://'")
        response = input("Doorgaan? (ja/nee): ").strip().lower()
        if response != 'ja':
            print("Geannuleerd.")
            sys.exit(1)
    
    # Lees bestaande .env
    lines = []
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    
    # Verwijder oude DATABASE_URL als die bestaat
    lines = [line for line in lines if not line.strip().startswith('DATABASE_URL=')]
    
    # Voeg nieuwe toe
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    
    # Voeg DATABASE_URL toe (na lege regel als laatste regel niet leeg is)
    if lines and lines[-1].strip():
        lines.append('\n')
    
    lines.append('# Database\n')
    lines.append(f'DATABASE_URL={database_url}\n')
    
    # Schrijf terug
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("\n" + "="*80)
    print("✅ DATABASE_URL succesvol toegevoegd aan .env")
    print("="*80)
    
    # Verifieer
    print("\nVerificatie:")
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'DATABASE_URL=' in content:
            # Toon alleen host voor veiligheid
            for line in content.split('\n'):
                if line.strip().startswith('DATABASE_URL='):
                    url_part = line.split('=')[1]
                    if '@' in url_part:
                        host_part = url_part.split('@')[1].split('/')[0]
                        print(f"  ✓ DATABASE_URL gevonden (host: {host_part})")
                    else:
                        print(f"  ✓ DATABASE_URL gevonden")
                    break


if __name__ == "__main__":
    try:
        # Accepteer DATABASE_URL als command-line argument
        database_url = None
        if len(sys.argv) > 1:
            database_url = sys.argv[1]
        
        add_database_url(database_url)
    except KeyboardInterrupt:
        print("\n\nGeannuleerd door gebruiker.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fout: {e}")
        sys.exit(1)
