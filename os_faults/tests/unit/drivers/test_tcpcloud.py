# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ddt
import mock

from os_faults.ansible import executor
from os_faults.api import node_collection
from os_faults.drivers import tcpcloud
from os_faults.tests.unit import fakes
from os_faults.tests.unit import test


@ddt.ddt
class TCPCloudManagementTestCase(test.TestCase):

    def setUp(self):
        super(TCPCloudManagementTestCase, self).setUp()
        self.fake_ansible_result = fakes.FakeAnsibleResult(
            payload={
                'stdout': 'cmp01.mk20.local:\n'
                          '  eth0:\n'
                          '    hwaddr: 09:7b:74:90:63:c2\n'
                          '    inet:\n'
                          '    - address: 10.0.0.2\n'
                          'cmp02.mk20.local:\n'
                          '  eth0:\n'
                          '    hwaddr: 09:7b:74:90:63:c3\n'
                          '    inet:\n'
                          '    - address: 10.0.0.3\n'
            })
        self.tcp_conf = {
            'address': 'tcp.local',
            'username': 'root',
        }
        self.get_nodes_cmd = (
            "salt -E '(ctl*|cmp*)' network.interfaces --out=yaml")

    @mock.patch('os_faults.ansible.executor.AnsibleRunner', autospec=True)
    def test_verify(self, mock_ansible_runner):
        ansible_runner_inst = mock_ansible_runner.return_value
        ansible_runner_inst.execute.side_effect = [
            [self.fake_ansible_result],
            [fakes.FakeAnsibleResult(payload={'stdout': ''}),
             fakes.FakeAnsibleResult(payload={'stdout': ''})],
        ]
        tcp_managment = tcpcloud.TCPCloudManagement(self.tcp_conf)
        tcp_managment.verify()

        ansible_runner_inst.execute.assert_has_calls([
            mock.call(['tcp.local'], {'command': self.get_nodes_cmd}),
            mock.call(['10.0.0.2', '10.0.0.3'], {'command': 'hostname'}),
        ])

    @mock.patch('os_faults.ansible.executor.AnsibleRunner', autospec=True)
    def test_get_nodes(self, mock_ansible_runner):
        ansible_runner_inst = mock_ansible_runner.return_value
        ansible_runner_inst.execute.side_effect = [[self.fake_ansible_result]]
        tcp_managment = tcpcloud.TCPCloudManagement(self.tcp_conf)
        nodes = tcp_managment.get_nodes()

        ansible_runner_inst.execute.assert_has_calls([
            mock.call(['tcp.local'], {'command': self.get_nodes_cmd}),
        ])

        hosts = [
            node_collection.Host(ip='10.0.0.2', mac='09:7b:74:90:63:c2',
                                 fqdn='cmp01.mk20.local'),
            node_collection.Host(ip='10.0.0.3', mac='09:7b:74:90:63:c3',
                                 fqdn='cmp02.mk20.local'),
        ]
        self.assertEqual(nodes.hosts, hosts)

    @mock.patch('os_faults.ansible.executor.AnsibleRunner', autospec=True)
    def test_execute_on_cloud(self, mock_ansible_runner):
        ansible_runner_inst = mock_ansible_runner.return_value
        ansible_runner_inst.execute.side_effect = [
            [self.fake_ansible_result],
            [fakes.FakeAnsibleResult(payload={'stdout': ''}),
             fakes.FakeAnsibleResult(payload={'stdout': ''})]
        ]
        tcp_managment = tcpcloud.TCPCloudManagement(self.tcp_conf)
        nodes = tcp_managment.get_nodes()
        result = tcp_managment.execute_on_cloud(
            nodes.get_ips(), {'command': 'mycmd'}, raise_on_error=False)

        ansible_runner_inst.execute.assert_has_calls([
            mock.call(['tcp.local'], {'command': self.get_nodes_cmd}),
            mock.call(['10.0.0.2', '10.0.0.3'], {'command': 'mycmd'}, []),
        ])

        self.assertEqual(result,
                         [fakes.FakeAnsibleResult(payload={'stdout': ''}),
                          fakes.FakeAnsibleResult(payload={'stdout': ''})])

    @mock.patch('os_faults.ansible.executor.AnsibleRunner', autospec=True)
    def test_get_nodes_fqdns(self, mock_ansible_runner):
        ansible_runner_inst = mock_ansible_runner.return_value
        ansible_runner_inst.execute.side_effect = [[self.fake_ansible_result]]
        tcp_managment = tcpcloud.TCPCloudManagement(self.tcp_conf)
        nodes = tcp_managment.get_nodes(fqdns=['cmp02.mk20.local'])

        hosts = [
            node_collection.Host(ip='10.0.0.3', mac='09:7b:74:90:63:c3',
                                 fqdn='cmp02.mk20.local'),
        ]
        self.assertEqual(nodes.hosts, hosts)

    @mock.patch('os_faults.ansible.executor.AnsibleRunner', autospec=True)
    @ddt.data(*tcpcloud.TCPCloudManagement.SERVICE_NAME_TO_CLASS.items())
    @ddt.unpack
    def test_get_service_nodes(self, service_name, service_cls,
                               mock_ansible_runner):
        ansible_runner_inst = mock_ansible_runner.return_value
        ansible_runner_inst.execute.side_effect = [
            [self.fake_ansible_result],
            [fakes.FakeAnsibleResult(payload={'stdout': ''},
                                     status=executor.STATUS_FAILED,
                                     host='10.0.0.2'),
             fakes.FakeAnsibleResult(payload={'stdout': ''},
                                     host='10.0.0.3')]
        ]

        tcp_managment = tcpcloud.TCPCloudManagement(self.tcp_conf)

        service = tcp_managment.get_service(service_name)
        self.assertIsInstance(service, service_cls)

        nodes = service.get_nodes()
        cmd = 'bash -c "ps ax | grep \'{}\'"'.format(service_cls.GREP)
        ansible_runner_inst.execute.assert_has_calls([
            mock.call(['tcp.local'], {'command': self.get_nodes_cmd}),
            mock.call(['10.0.0.2', '10.0.0.3'],
                      {'command': cmd}, []),
        ])

        hosts = [
            node_collection.Host(ip='10.0.0.3', mac='09:7b:74:90:63:c3',
                                 fqdn='cmp02.mk20.local'),
        ]
        self.assertEqual(nodes.hosts, hosts)
