from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from cosmetics.models import BotSkin, OwnedSkin
from matches.models import MatchType
from shop.models import CoinPackage
from accounts.models import Profile

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data: admin user, match types, skins, coin packages'

    def handle(self, *args, **options):
        # Create admin user
        if not User.objects.filter(username='Vic-Nas').exists():
            admin = User.objects.create_superuser('Vic-Nas', 'admin@dash.game', 'Brajulia2000')
            self.stdout.write(self.style.SUCCESS('✓ Admin user created: Vic-Nas / Brajulia2000'))
        else:
            admin = User.objects.get(username='Vic-Nas')
            self.stdout.write(self.style.WARNING('Admin user already exists'))

        # Create default bot skins
        default_skins = [
            {'name':'Classic Blue', 'description':'Default starter skin', 'colorPrimary':'#3b82f6', 'colorSecondary':'#1e40af', 'trailEffect':'NONE', 'price':0, 'isDefault':True, 'rarity':'COMMON', 'displayOrder':1},
            {'name':'Fire Red', 'description':'Blazing red with fire trail', 'colorPrimary':'#ef4444', 'colorSecondary':'#991b1b', 'trailEffect':'FIRE', 'price':50, 'isDefault':False, 'rarity':'RARE', 'displayOrder':2},
            {'name':'Ice Queen', 'description':'Frosty blue with ice trail', 'colorPrimary':'#06b6d4', 'colorSecondary':'#0e7490', 'trailEffect':'ICE', 'price':100, 'isDefault':False, 'rarity':'EPIC', 'displayOrder':3},
            {'name':'Gold Legend', 'description':'Golden glory with sparkle trail', 'colorPrimary':'#fbbf24', 'colorSecondary':'#f59e0b', 'trailEffect':'SPARKLE', 'price':500, 'isDefault':False, 'rarity':'LEGENDARY', 'displayOrder':4},
        ]
        for skin_data in default_skins:
            BotSkin.objects.get_or_create(name=skin_data['name'], defaults=skin_data)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(default_skins)} bot skins'))

        # Create match types
        match_types = [
            {'name':'Quick Match', 'description':'Fast 4-player match', 'entryFee':5, 'gridSize':25, 'speed':'FAST', 'playersRequired':4, 'maxPlayers':4, 'livesPerPlayer':0, 'wallSpawnInterval':5, 'allowExtraLives':False, 'displayOrder':1},
            {'name':'Standard Arena', 'description':'Classic 6-player match', 'entryFee':10, 'gridSize':30, 'speed':'MEDIUM', 'playersRequired':6, 'maxPlayers':6, 'livesPerPlayer':1, 'wallSpawnInterval':5, 'allowExtraLives':True, 'displayOrder':2},
            {'name':'Speed Demon', 'description':'Extreme speed, 4 players', 'entryFee':15, 'gridSize':25, 'speed':'EXTREME', 'playersRequired':4, 'maxPlayers':4, 'livesPerPlayer':0, 'wallSpawnInterval':3, 'allowExtraLives':False, 'displayOrder':3},
            {'name':'Big Arena', 'description':'8-player chaos', 'entryFee':25, 'gridSize':35, 'speed':'MEDIUM', 'playersRequired':8, 'maxPlayers':8, 'livesPerPlayer':2, 'wallSpawnInterval':6, 'allowExtraLives':True, 'maxExtraLives':3, 'displayOrder':4},
            {'name':'High Stakes', 'description':'Winner takes all, 6 players', 'entryFee':50, 'gridSize':30, 'speed':'FAST', 'playersRequired':6, 'maxPlayers':6, 'livesPerPlayer':1, 'wallSpawnInterval':4, 'allowExtraLives':True, 'displayOrder':5},
        ]
        for mt_data in match_types:
            MatchType.objects.get_or_create(name=mt_data['name'], defaults=mt_data)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(match_types)} match types'))

        # Create coin packages
        packages = [
            {'name':'Starter Pack', 'description':'Get started with 100 coins', 'coins':100, 'price':0.99, 'displayOrder':1},
            {'name':'Standard Pack', 'description':'500 coins for casual play', 'coins':500, 'price':4.99, 'displayOrder':2},
            {'name':'Premium Pack', 'description':'1200 coins + bonus', 'coins':1200, 'price':9.99, 'displayOrder':3},
            {'name':'Mega Bundle', 'description':'Best value! 3000 coins', 'coins':3000, 'price':19.99, 'displayOrder':4},
        ]
        for pkg_data in packages:
            CoinPackage.objects.get_or_create(name=pkg_data['name'], defaults=pkg_data)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(packages)} coin packages'))

        # Give admin the default skin
        default_skin = BotSkin.objects.get(name='Classic Blue')
        OwnedSkin.objects.get_or_create(player=admin, skin=default_skin)
        admin_profile, _ = Profile.objects.get_or_create(user=admin, defaults={'coins': 5000})
        admin_profile.currentSkin = default_skin
        admin_profile.save()
        self.stdout.write(self.style.SUCCESS('✓ Admin equipped with default skin'))

        self.stdout.write(self.style.SUCCESS('\n🎮 Seed complete! Login: Vic-Nas / Brajulia2000'))
