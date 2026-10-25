"""Package checks, adapted from reason-machines/reason-plugins tests."""
import json, re, struct, unittest, posixpath
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/x402m'
KEBAB = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
PATH_FIELDS = ['logo', 'rules', 'skills', 'agents', 'commands', 'hooks', 'mcpServers']
COMPONENTS = {'rules': ['description'], 'commands': ['name', 'description']}
SECRET = re.compile(r'(sk_live_|sk_test_|-----BEGIN [A-Z ]*PRIVATE KEY|Authorization:\s*Bearer\s+\w|ghp_[A-Za-z0-9]{20}|"(api_?key|secret|token|privateKey)"\s*:)', re.I)
FORBIDDEN_CLAIMS = [r'npm install\s+\S*x402m', r'official x402 (/\.well-known )?standard(?!,)', r'EVM relay (is )?(live|working|available)']


def frontmatter(path):
    text = path.read_text()
    if not text.startswith('---\n'):
        return None
    block = text[4:text.index('\n---\n', 4)]
    return {k.strip(): v.strip() for k, v in (l.split(':', 1) for l in block.split('\n') if ':' in l)}


def files():
    return [p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and p.suffix not in {'.png', '.pyc'} and p.parent.name != 'tests']


class Manifests(unittest.TestCase):
    def test_json_parses(self):
        found = [p for p in ROOT.rglob('*.json') if '.git' not in p.parts]
        self.assertGreaterEqual(len(found), 7)
        for p in found:
            json.loads(p.read_text())

    def test_versions_and_names_agree(self):
        versions = {json.loads((PLUGIN / f).read_text())['version'] for f in
                    ['plugin.json', '.codex-plugin/plugin.json', '.claude-plugin/plugin.json', '.cursor-plugin/plugin.json']}
        versions.add(json.loads((ROOT / '.cursor-plugin/marketplace.json').read_text())['metadata']['version'])
        self.assertEqual(len(versions), 1, versions)
        for m in ['.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json', '.cursor-plugin/marketplace.json']:
            d = json.loads((ROOT / m).read_text())
            self.assertEqual([p['name'] for p in d['plugins']], ['x402m'])

    def test_portable_matches_codex_interface(self):
        portable = json.loads((PLUGIN / 'plugin.json').read_text())
        codex = json.loads((PLUGIN / '.codex-plugin/plugin.json').read_text())
        iface = portable['extensions']['com.openai']['interface']
        self.assertEqual(iface, codex['interface'])
        self.assertLessEqual(len(iface['shortDescription']), 30)
        for key in ['composerIcon', 'logo', 'logoDark']:
            data = (PLUGIN / iface[key]).read_bytes()
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')

    def test_cursor_paths_safe_and_present(self):
        plugin = json.loads((PLUGIN / '.cursor-plugin/plugin.json').read_text())
        self.assertRegex(plugin['name'], KEBAB)
        for f in PATH_FIELDS:
            v = plugin.get(f)
            if isinstance(v, str):
                self.assertFalse(v.startswith('/') or posixpath.normpath(v).startswith('..'), v)
                self.assertTrue((PLUGIN / v).exists(), v)
        width, height = struct.unpack('>II', (PLUGIN / plugin['logo']).read_bytes()[16:24])
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 256)


class Components(unittest.TestCase):
    def test_frontmatter(self):
        skill = frontmatter(PLUGIN / 'skills/x402m/SKILL.md')
        self.assertEqual(skill['name'], 'x402m')
        self.assertLessEqual(len(skill['description']), 1024)
        names = ['x402m']
        for folder, keys in COMPONENTS.items():
            for p in (PLUGIN / folder).iterdir():
                fm = frontmatter(p)
                self.assertIsNotNone(fm, p)
                for k in keys:
                    self.assertTrue(fm.get(k), f'{p}:{k}')
                if 'name' in keys:
                    self.assertEqual(fm['name'], p.stem)
                    names.append(fm['name'])
        self.assertEqual(len(names), len(set(names)))

    def test_skill_teaches_real_capabilities(self):
        text = (PLUGIN / 'skills/x402m/SKILL.md').read_text()
        for cap in ['x402m.register', 'x402m.send', 'x402m.inbox', 'x402m.ack',
                    'https://musebook.trade/api/x402m/discovery', 'https://bot.musebook.trade',
                    'https://mcp.reasonmachines.com/mcp', 'github.com/Solizardking/x402-messaging']:
            self.assertIn(cap, text)


class Safety(unittest.TestCase):
    def test_no_secrets_hooks_or_executables(self):
        for p in files():
            self.assertNotRegex(p.read_text(), SECRET, str(p))
            self.assertNotIn(p.suffix, {'.sh', '.js', '.mjs', '.ts', '.exe'}, str(p))
        self.assertFalse(list(ROOT.rglob('hooks*.json')))

    def test_no_mcp_server_bundled_reason_is_opt_in(self):
        for f in ['.codex-plugin/plugin.json', '.cursor-plugin/plugin.json', '.claude-plugin/plugin.json']:
            self.assertNotIn('mcpServers', json.loads((PLUGIN / f).read_text()))
        self.assertFalse(list(PLUGIN.rglob('*mcp.json')))
        self.assertIn('opt-in', (PLUGIN / 'skills/x402m/SKILL.md').read_text())

    def test_proposals_only_and_experimental(self):
        for p in [PLUGIN / 'skills/x402m/SKILL.md', ROOT / 'README.md']:
            t = p.read_text().lower()
            self.assertIn('experimental', t)
            self.assertIn('never', t)
            self.assertIn('spending authority', t)

    def test_no_forbidden_claims(self):
        for p in files():
            if p.parent.name == 'tests':
                continue
            for claim in FORBIDDEN_CLAIMS:
                self.assertNotRegex(p.read_text(), re.compile(claim, re.I), str(p))


if __name__ == '__main__':
    unittest.main()
