#
# Copyright 2015 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import

import errno
import types
import unittest

from contextlib import contextmanager
from mock import MagicMock
from mock import patch

libvirt_mock = types.ModuleType('libvirt')

libvirt_mock.VIR_NETWORK_UPDATE_COMMAND_ADD_LAST = 3
libvirt_mock.VIR_NETWORK_UPDATE_COMMAND_DELETE = 2
libvirt_mock.VIR_NETWORK_UPDATE_COMMAND_MODIFY = 1
libvirt_mock.VIR_NETWORK_SECTION_DNS_HOST = 10
libvirt_mock.VIR_NETWORK_SECTION_IP_DHCP_HOST = 4
libvirt_mock.VIR_NETWORK_UPDATE_AFFECT_CONFIG = 2
libvirt_mock.VIR_NETWORK_UPDATE_AFFECT_LIVE = 1


class MockLibvirtError(Exception):
    pass

libvirt_mock.libvirtError = MockLibvirtError


@contextmanager
def xmldesc_mock(xmldesc=None):
    with patch.dict('sys.modules', {'libvirt': libvirt_mock}):
        from . import libvirt as driver

        mock_xml = MagicMock()
        mock_xml.XMLDesc.return_value = xmldesc

        yield driver, mock_xml


class TestNetwork(unittest.TestCase):
    NETXML_DOMAIN = """\
<network>
  <domain name='mydomain.example.com'/>
</network>
"""

    NETXML_DOMAIN_EMPTY = """\
<network>
  <domain/>
</network>
"""

    NETXML_DOMAIN_MISSING = """\
<network>
  <domain/>
</network>
"""

    def test_network_name(self):
        with xmldesc_mock(self.NETXML_DOMAIN) as (driver, net):
            name = driver._get_network_domainname(net)
            net.XMLDesc.assert_called_with()
        assert name == 'mydomain.example.com'

    def test_network_name_empty(self):
        with xmldesc_mock(self.NETXML_DOMAIN_EMPTY) as (driver, net):
            name = driver._get_network_domainname(net)
            net.XMLDesc.assert_called_with()
        assert name is None

    def test_network_name_missing(self):
        with xmldesc_mock(self.NETXML_DOMAIN_MISSING) as (driver, net):
            name = driver._get_network_domainname(net)
            net.XMLDesc.assert_called_with()
        assert name is None


class TestStorage(unittest.TestCase):
    POOLXML_PATH_DIR = """\
<pool type='dir'>
  <target>
    <path>/var/lib/libvirt/images</path>
  </target>
</pool>
"""

    POOLXML_PATH_ISCSI = """\
<pool type='iscsi'>
  <target>
    <path>/var/lib/libvirt/images</path>
  </target>
</pool>
"""

    def test_pool_path_dir(self):
        with xmldesc_mock(self.POOLXML_PATH_DIR) as (driver, pool):
            path = driver._get_pool_path(pool)
            pool.XMLDesc.assert_called_with()
        assert path == '/var/lib/libvirt/images'

    def test_pool_path_iscsi(self):
        with xmldesc_mock(self.POOLXML_PATH_ISCSI) as (driver, pool):
            try:
                driver._get_pool_path(pool)
            except OSError as e:
                assert e.errno == errno.ENOENT


class TestDomain(unittest.TestCase):
    DOMXML_ONE_MACADDR = """\
<domain type='kvm'>
  <devices>
    <interface type='network'>
      <mac address='52:54:00:a0:b0:01'/>
      <source network='default'/>
    </interface>
  </devices>
</domain>
"""

    DOMXML_MULTI_MACADDR = """\
<domain type='kvm'>
  <devices>
    <interface type='network'>
      <mac address='52:54:00:a0:b0:01'/>
      <source network='default'/>
    </interface>
    <interface type='network'>
      <mac address='52:54:00:a0:b0:02'/>
      <source network='default'/>
    </interface>
    <interface type='network'>
      <mac address='52:54:00:a0:b0:03'/>
      <source network='othernet1'/>
    </interface>
  </devices>
</domain>
"""

    def test_get_domain_one_mac_addresses(self):
        with xmldesc_mock(self.DOMXML_ONE_MACADDR) as (driver, domain):
            macs = list(driver._get_domain_mac_addresses(domain))
        domain.XMLDesc.assert_called_with()
        assert macs == [
            {'mac': '52:54:00:a0:b0:01', 'network': 'default'},
        ]

    def test_get_domain_multi_mac_addresses(self):
        with xmldesc_mock(self.DOMXML_MULTI_MACADDR) as (driver, domain):
            macs = list(driver._get_domain_mac_addresses(domain))
        domain.XMLDesc.assert_called_with()
        assert macs == [
            {'mac': '52:54:00:a0:b0:01', 'network': 'default'},
            {'mac': '52:54:00:a0:b0:02', 'network': 'default'},
            {'mac': '52:54:00:a0:b0:03', 'network': 'othernet1'},
        ]


class TestNetworkDhcpHosts(unittest.TestCase):
    NETXML_DHCP = """\
<network>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <host mac='52:54:00:a1:b2:01' name='test01' ip='192.168.122.2'/>
      <host mac='52:54:00:a1:b2:02' name='test02' ip='192.168.122.3'/>
      <host mac='52:54:00:a1:b2:03' ip='192.168.122.4'/>
    </dhcp>
  </ip>
</network>
"""

    NETXML_DHCP_EXPECTED = [
        {'mac': '52:54:00:a1:b2:01', 'name': 'test01',
         'ip': '192.168.122.2'},
        {'mac': '52:54:00:a1:b2:02', 'name': 'test02',
         'ip': '192.168.122.3'},
        {'mac': '52:54:00:a1:b2:03', 'name': None,
         'ip': '192.168.122.4'},
    ]

    NETXML_DHCP_EMPTY = """\
<network>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp/>
  </ip>
</network>
"""

    NETXML_DHCP_MISSING = """\
<network>
  <ip address='192.168.122.1' netmask='255.255.255.0'/>
</network>
"""

    def test_dhcp_hosts(self):
        with xmldesc_mock(self.NETXML_DHCP) as (driver, net):
            hosts = list(driver._get_network_dhcp_hosts(net))
        net.XMLDesc.assert_called_with()
        assert hosts == self.NETXML_DHCP_EXPECTED

    def test_dhcp_hosts_empty(self):
        with xmldesc_mock(self.NETXML_DHCP_EMPTY) as (driver, net):
            hosts = list(driver._get_network_dhcp_hosts(net))
        net.XMLDesc.assert_called_with()
        assert hosts == list()

    def test_dhcp_hosts_missing(self):
        with xmldesc_mock(self.NETXML_DHCP_MISSING) as (driver, net):
            hosts = list(driver._get_network_dhcp_hosts(net))
        net.XMLDesc.assert_called_with()
        assert hosts == list()

    def test_add_dhcp_host(self):
        with xmldesc_mock() as (driver, net):
            driver._add_network_dhcp_host(
                net, 'test01', '52:54:00:a1:b2:01', '192.168.122.2')
        expected_xml = ('<host mac="52:54:00:a1:b2:01" name="test01" '
                        'ip="192.168.122.2"/>')
        net.update.assert_called_with(3, 4, 0, expected_xml.encode(), 3)

    def test_del_dhcp_host(self):
        with xmldesc_mock() as (driver, net):
            driver._del_network_dhcp_host(net, '192.168.122.2')
        expected_xml = '<host ip="192.168.122.2"/>'
        net.update.assert_called_with(2, 4, 0, expected_xml.encode(), 3)


class TestNetworkDnsHosts(unittest.TestCase):
    def test_add_dns_host(self):
        with xmldesc_mock() as (driver, net):
            driver._add_network_host(net, 'test01', '192.168.122.2')
        expected_xml = ('<host ip="192.168.122.2">'
                        '<hostname>test01</hostname></host>')
        net.update.assert_called_with(3, 10, 0, expected_xml.encode(), 3)

    def test_del_dns_host(self):
        with xmldesc_mock() as (driver, net):
            driver._del_network_host(net, '192.168.122.2')
        expected_xml = '<host ip="192.168.122.2"/>'
        net.update.assert_called_with(2, 10, 0, expected_xml.encode(), 3)
