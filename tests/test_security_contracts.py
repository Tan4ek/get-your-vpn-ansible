import configparser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from jinja2 import Environment, StrictUndefined, UndefinedError
import yaml


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_KEY = "test-only-key-" + "a" * 32


class SecurityContracts(unittest.TestCase):
    def setUp(self):
        self.variables = yaml.safe_load(
            (ROOT / "inventory-example/group_vars/all.yml").read_text()
        )
        self.variables.update(
            get_your_vpn_config_api_key=SYNTHETIC_KEY,
            get_your_vpn_openvpn_port=18090,
            get_your_vpn_ss_port=18080,
            get_your_vpn_prometheus_port=19090,
            get_your_vpn_openvpn_prometheus_exporter_port=19176,
            get_your_vpn_ss_prometheus_exporter_port=19091,
        )
        self.tasks = yaml.safe_load(
            (ROOT / "roles/get-your-vpn-config/tasks/main.yml").read_text()
        )

    def render(self, role, filename):
        template = ROOT / "roles" / role / "templates" / filename
        return Environment(undefined=StrictUndefined).from_string(
            template.read_text()
        ).render(self.variables)

    def test_management_ports_are_local_and_vpn_ports_remain_public(self):
        for role, service, expected_ports in (
            ("get-your-vpn-openvpn", "openvpn", ["1194:1194/udp", "127.0.0.1:18090:8090"]),
            ("get-your-vpn-ss", "ss-server-user-manager", [
                "127.0.0.1:18080:8080", "443:9000",
                "127.0.0.1:19091:9091",
            ]),
            ("get-your-vpn-prometheus", "get-your-vpn-prometheus", ["127.0.0.1:19090:9090"]),
            ("get-your-vpn-openvpn-prometheus-exporter", "get-your-vpn-openvpn-prometheus-exporter",
             ["127.0.0.1:19176:9176"]),
        ):
            with self.subTest(role=role):
                compose = yaml.safe_load(self.render(role, "docker-compose.yml.j2"))
                self.assertEqual(compose["services"][service]["ports"], expected_ports)
                self.assertEqual(
                    compose["networks"]["default"]["external"]["name"], "get-your-vpn"
                )

    def test_internal_addresses_ignore_published_port_overrides(self):
        config = configparser.ConfigParser()
        config.read_string(self.render("get-your-vpn-config", "config.ini.j2"))
        for section, key, name, port in (
            ("openvpn-http-api", "Uri", "openvpn", 8090),
            ("outline-ss-server-user-manager", "Uri", "ss", 8080),
            ("vpn-metrics", "PrometheusUri", "prometheus", 9090),
        ):
            with self.subTest(section=section):
                hostname = self.variables[f"get_your_vpn_{name}_container_name"]
                self.assertEqual(config[section][key], f"http://{hostname}:{port}")
        self.assertEqual(config["admin"]["XApiKey"], SYNTHETIC_KEY)

    def test_metric_scrapes_ignore_published_port_overrides(self):
        config = yaml.safe_load(self.render("get-your-vpn-prometheus", "prometheus.yml.j2"))
        targets = {
            job["job_name"]: job["static_configs"][0]["targets"]
            for job in config["scrape_configs"]
        }
        self.assertEqual(targets, {
            "outline-server": [f"{self.variables['get_your_vpn_ss_container_name']}:9091"],
            "openvpn-server": [
                f"{self.variables['get_your_vpn_openvpn_prometheus_exporter_container_name']}:9176"
            ],
        })

    def test_config_key_has_no_template_default(self):
        del self.variables["get_your_vpn_config_api_key"]
        with self.assertRaises(UndefinedError):
            self.render("get-your-vpn-config", "config.ini.j2")

    def test_secret_file_is_protected_and_frontend_port_is_preserved(self):
        task = next(task for task in self.tasks if task["name"] == "prepare config")
        template = task["ansible.builtin.template"]
        self.assertEqual((template["owner"], template["group"], template["mode"]),
                         ("root", "root", "0600"))
        self.assertTrue(task["no_log"])
        self.assertFalse(task["diff"])
        compose = yaml.safe_load(self.render("get-your-vpn-config", "docker-compose.yml.j2"))
        service = compose["services"]["get-your-vpn-config"]
        self.assertIn("./config.ini:/app/config.ini:ro", service["volumes"])
        self.assertEqual(service["ports"],
                         [f"{self.variables['get_your_vpn_config_container_port']}:8080"])

    def test_actual_ansible_assertion_accepts_only_valid_explicit_keys(self):
        self.assertEqual(self.tasks[0]["ansible.builtin.import_tasks"], "validate.yml")
        validation = yaml.safe_load(
            (ROOT / "roles/get-your-vpn-config/tasks/validate.yml").read_text()
        )
        assertion = validation[0]
        self.assertIn("ansible.builtin.assert", assertion)
        self.assertTrue(assertion["no_log"])
        deployment = yaml.safe_load((ROOT / "deploy-application.yml").read_text())[0]
        pre_tasks = deployment["pre_tasks"]
        self.assertEqual(pre_tasks[0]["ansible.builtin.import_role"],
                         {"name": "get-your-vpn-config", "tasks_from": "validate"})
        executable = Path(sys.executable).with_name("ansible-playbook")
        if not executable.is_file():
            executable = Path(shutil.which("ansible-playbook") or "ansible-playbook")
        self.assertTrue(Path(executable).is_file(), "Run tests in the Ansible Python environment")
        cases = [
            ({}, False),
            ({"get_your_vpn_config_api_key": "supersecureapikey"}, False),
            ({"get_your_vpn_config_api_key": 12345}, False),
            ({"get_your_vpn_config_api_key": SYNTHETIC_KEY + "\n"}, False),
            ({"get_your_vpn_config_api_key": SYNTHETIC_KEY + "%"}, False),
            ({"get_your_vpn_config_api_key": SYNTHETIC_KEY}, True),
        ]
        with tempfile.TemporaryDirectory() as directory:
            playbook = Path(directory) / "assert-key.yml"
            environment = os.environ | {
                "ANSIBLE_LOCAL_TEMP": str(Path(directory) / "ansible-local"),
                "ANSIBLE_REMOTE_TEMP": str(Path(directory) / "ansible-remote"),
                "ANSIBLE_ROLES_PATH": str(ROOT / "roles"),
            }
            for variables, valid in cases:
                with self.subTest(valid=valid, variables=variables):
                    playbook.write_text(yaml.safe_dump([{
                        "name": "Check synthetic API key only",
                        "hosts": "localhost",
                        "connection": "local",
                        "gather_facts": False,
                        "vars": variables,
                        "pre_tasks": pre_tasks,
                        "tasks": [{"ansible.builtin.debug": {"msg": "VALIDATION_PASSED"}}],
                    }]))
                    result = subprocess.run(
                        [str(executable), "-i", "localhost,", str(playbook)],
                        cwd=directory, env=environment, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                    )
                    self.assertIn(assertion["name"], result.stdout)
                    self.assertEqual(result.returncode == 0, valid, result.stdout)
                    self.assertEqual("VALIDATION_PASSED" in result.stdout, valid, result.stdout)
                    self.assertNotIn(SYNTHETIC_KEY, result.stdout)


if __name__ == "__main__":
    unittest.main()
