from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from exchange.models import PartListing


class Command(BaseCommand):
    help = 'Create fictional local demo listings and three demo accounts. Existing data is preserved.'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='ReLoopDemo!2026', help='Password for newly created demo accounts.')

    def handle(self, *args, **options):
        if len(options['password']) < 12:
            raise CommandError('Use a demo password of at least 12 characters.')
        users = {}
        for name in ['donor', 'repairer', 'moderator']:
            user, created = User.objects.get_or_create(username=name)
            if created:
                user.set_password(options['password'])
                user.is_staff = name == 'moderator'
                user.is_superuser = name == 'moderator'
                user.save()
                self.stdout.write(f'Created {name}.')
            users[name] = user
        examples = [
            ('14-inch laptop display', 'screen', 'DEMO-LCD-140-A', 'tested', 'DemoBook 14 A1\nDemoBook 14 A2', 'Campus repair lab', 'Panel powers on and displays the test pattern. Connector and mounting points need a physical compatibility check.'),
            ('8 GB DDR4 laptop memory', 'memory', 'DEMO-RAM-8-2666', 'tested', 'DemoBook 15 M1', 'Pune university area', 'Memory passed a demonstration test. Check DDR generation, capacity limits and module form factor.'),
            ('256 GB SATA SSD', 'storage', 'DEMO-SSD-256-SATA', 'tested', 'DemoDesk S1', 'Campus repair lab', 'Drive formatted for the fictional demonstration. Check interface and drive bay before reserving.'),
            ('Compact laptop keyboard', 'keyboard', 'DEMO-KBD-13-US', 'tested', 'DemoBook 13 K1', 'Kothrud repair club', 'All keys responded in a demonstration test. Keyboard layout and ribbon connector must match.'),
            ('Laptop display assembly', 'screen', 'DEMO-LCD-156-B', 'untested', 'DemoBook 15 B1', 'Campus repair lab', 'Unverified assembly from a non-booting demo device. Condition needs assessment before use.'),
            ('4 GB desktop memory', 'memory', 'DEMO-RAM-4-DIMM', 'tested', 'DemoDesk D2', 'Pune university area', 'A single memory module. Verify generation, voltage and motherboard support.'),
            ('Laptop trackpad module', 'other', 'DEMO-PAD-14-C', 'repair', 'DemoBook 14 C1', 'Kothrud repair club', 'Intermittent left click in the demonstration scenario. Suitable for diagnosis or component recovery.'),
            ('500 GB hard drive', 'storage', 'DEMO-HDD-500-SATA', 'untested', 'DemoDesk S2', 'Campus repair lab', 'No test evidence supplied. The repairer must assess health and securely erase any real drive before reuse.'),
        ]
        count = 0
        for title, category, code, condition, models, area, description in examples:
            _, created = PartListing.objects.get_or_create(owner=users['donor'], part_code=code, defaults={
                'title': title, 'category': category, 'manufacturer': 'ExampleTech (demo)',
                'condition': condition, 'supported_models': models, 'pickup_area': area,
                'description': 'FICTIONAL DEMO LISTING. Codes, devices and test results are sample data. ' + description,
            })
            count += created
        self.stdout.write(self.style.SUCCESS(f'Added {count} fictional listings. Existing accounts and listings were not reset.'))
        self.stdout.write('Demo users: donor, repairer, moderator. New accounts use the supplied --password (default: ReLoopDemo!2026).')
