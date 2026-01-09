from django.core.management.base import BaseCommand
from game.models import playerScore


class Command(BaseCommand):
    help = "Seed initial game data required for play (e.g., baseline high scores)."

    def handle(self, *args, **options):
        if playerScore.objects.exists():
            self.stdout.write(self.style.WARNING("playerScore already has data; skipping seed."))
            return
        seeds = [
            {"playerName": "Ada", "scoreValue": 42},
            {"playerName": "Linus", "scoreValue": 37},
            {"playerName": "Grace", "scoreValue": 29},
            {"playerName": "Ken", "scoreValue": 21},
            {"playerName": "Guido", "scoreValue": 13},
        ]
        for s in seeds:
            playerScore.objects.create(**s)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(seeds)} playerScore rows."))
