from collections import OrderedDict
import subprocess
import apt_pkg

from mock import patch, call
from testtools import TestCase
from tests.helpers import patch_open
from tests.helpers import mock_open as mocked_open
import six

from charmhelpers.core import host


MOUNT_LINES = ("""
rootfs / rootfs rw 0 0
sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
udev /dev devtmpfs rw,relatime,size=8196788k,nr_inodes=2049197,mode=755 0 0
devpts /dev/pts devpts """
               """rw,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 0 0
""").strip().split('\n')

LSB_RELEASE = '''DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=13.10
DISTRIB_CODENAME=saucy
DISTRIB_DESCRIPTION="Ubuntu Saucy Salamander (development branch)"
'''

IP_LINE_ETH0 = b"""
2: eth0: <BROADCAST,MULTICAST,SLAVE,UP,LOWER_UP> mtu 1500 qdisc mq master bond0 state UP qlen 1000
    link/ether e4:11:5b:ab:a7:3c brd ff:ff:ff:ff:ff:ff
"""

IP_LINE_ETH0_VLAN = b"""
6: eth0.10@eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default
    link/ether 08:00:27:16:b9:5f brd ff:ff:ff:ff:ff:ff
"""

IP_LINE_ETH1 = b"""
3: eth1: <BROADCAST,MULTICAST> mtu 1546 qdisc noop state DOWN qlen 1000
    link/ether e4:11:5b:ab:a7:3c brd ff:ff:ff:ff:ff:ff
"""

IP_LINE_HWADDR = b"""2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP qlen 1000\    link/ether e4:11:5b:ab:a7:3c brd ff:ff:ff:ff:ff:ff"""

IP_LINES = IP_LINE_ETH0 + IP_LINE_ETH1 + IP_LINE_ETH0_VLAN

IP_LINE_BONDS = b"""
6: bond0.10@bond0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default
link/ether 08:00:27:16:b9:5f brd ff:ff:ff:ff:ff:ff
"""


class HelpersTest(TestCase):
    @patch('subprocess.call')
    def test_runs_service_action(self, mock_call):
        mock_call.return_value = 0
        action = 'some-action'
        service_name = 'foo-service'

        result = host.service(action, service_name)

        self.assertTrue(result)
        mock_call.assert_called_with(['service', service_name, action])

    @patch('subprocess.call')
    def test_returns_false_when_service_fails(self, mock_call):
        mock_call.return_value = 1
        action = 'some-action'
        service_name = 'foo-service'

        result = host.service(action, service_name)

        self.assertFalse(result)
        mock_call.assert_called_with(['service', service_name, action])

    @patch.object(host, 'service')
    def test_starts_a_service(self, service):
        service_name = 'foo-service'
        service.side_effect = [True]
        self.assertTrue(host.service_start(service_name))

        service.assert_called_with('start', service_name)

    @patch.object(host, 'service')
    def test_stops_a_service(self, service):
        service_name = 'foo-service'
        service.side_effect = [True]
        self.assertTrue(host.service_stop(service_name))

        service.assert_called_with('stop', service_name)

    @patch.object(host, 'service')
    def test_restarts_a_service(self, service):
        service_name = 'foo-service'
        service.side_effect = [True]
        self.assertTrue(host.service_restart(service_name))

        service.assert_called_with('restart', service_name)

    @patch.object(host, 'service')
    def test_reloads_a_service(self, service):
        service_name = 'foo-service'
        service.side_effect = [True]
        self.assertTrue(host.service_reload(service_name))

        service.assert_called_with('reload', service_name)

    @patch.object(host, 'service')
    def test_failed_reload_restarts_a_service(self, service):
        service_name = 'foo-service'
        service.side_effect = [False, True]
        self.assertTrue(
            host.service_reload(service_name, restart_on_failure=True))

        service.assert_has_calls([
            call('reload', service_name),
            call('restart', service_name)
        ])

    @patch.object(host, 'service')
    def test_failed_reload_without_restart(self, service):
        service_name = 'foo-service'
        service.side_effect = [False]
        self.assertFalse(host.service_reload(service_name))

        service.assert_called_with('reload', service_name)

    @patch.object(host, 'service')
    def test_start_a_service_fails(self, service):
        service_name = 'foo-service'
        service.side_effect = [False]
        self.assertFalse(host.service_start(service_name))

        service.assert_called_with('start', service_name)

    @patch.object(host, 'service')
    def test_stop_a_service_fails(self, service):
        service_name = 'foo-service'
        service.side_effect = [False]
        self.assertFalse(host.service_stop(service_name))

        service.assert_called_with('stop', service_name)

    @patch.object(host, 'service')
    def test_restart_a_service_fails(self, service):
        service_name = 'foo-service'
        service.side_effect = [False]
        self.assertFalse(host.service_restart(service_name))

        service.assert_called_with('restart', service_name)

    @patch.object(host, 'service')
    def test_reload_a_service_fails(self, service):
        service_name = 'foo-service'
        service.side_effect = [False]
        self.assertFalse(host.service_reload(service_name))

        service.assert_called_with('reload', service_name)

    @patch.object(host, 'service')
    def test_failed_reload_restarts_a_service_fails(self, service):
        service_name = 'foo-service'
        service.side_effect = [False, False]
        self.assertFalse(
            host.service_reload(service_name, restart_on_failure=True))

        service.assert_has_calls([
            call('reload', service_name),
            call('restart', service_name)
        ])

    @patch('subprocess.check_output')
    def test_service_running_on_stopped_service(self, check_output):
        check_output.return_value = b'foo stop/waiting'
        self.assertFalse(host.service_running('foo'))

    @patch('subprocess.check_output')
    def test_service_running_on_running_service(self, check_output):
        check_output.return_value = b'foo start/running, process 23871'
        self.assertTrue(host.service_running('foo'))

    @patch('subprocess.check_output')
    def test_service_running_on_unknown_service(self, check_output):
        exc = subprocess.CalledProcessError(1, ['status'])
        check_output.side_effect = exc
        self.assertFalse(host.service_running('foo'))

    @patch('pwd.getpwnam')
    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_adds_a_user_if_it_doesnt_exist(self, log, check_call, getpwnam):
        username = 'johndoe'
        password = 'eodnhoj'
        shell = '/bin/bash'
        existing_user_pwnam = KeyError('user not found')
        new_user_pwnam = 'some user pwnam'

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]

        result = host.adduser(username, password)

        self.assertEqual(result, new_user_pwnam)
        check_call.assert_called_with([
            'useradd',
            '--create-home',
            '--shell', shell,
            '--password', password,
            username
        ])
        getpwnam.assert_called_with(username)

    @patch('pwd.getpwnam')
    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_doesnt_add_user_if_it_already_exists(self, log, check_call,
                                                  getpwnam):
        username = 'johndoe'
        password = 'eodnhoj'
        existing_user_pwnam = 'some user pwnam'

        getpwnam.return_value = existing_user_pwnam

        result = host.adduser(username, password)

        self.assertEqual(result, existing_user_pwnam)
        self.assertFalse(check_call.called)
        getpwnam.assert_called_with(username)

    @patch('pwd.getpwnam')
    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_adds_a_user_with_different_shell(self, log, check_call, getpwnam):
        username = 'johndoe'
        password = 'eodnhoj'
        shell = '/bin/zsh'
        existing_user_pwnam = KeyError('user not found')
        new_user_pwnam = 'some user pwnam'

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]

        result = host.adduser(username, password, shell=shell)

        self.assertEqual(result, new_user_pwnam)
        check_call.assert_called_with([
            'useradd',
            '--create-home',
            '--shell', shell,
            '--password', password,
            username
        ])
        getpwnam.assert_called_with(username)

    @patch('pwd.getpwnam')
    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_adds_a_systemuser(self, log, check_call, getpwnam):
        username = 'johndoe'
        existing_user_pwnam = KeyError('user not found')
        new_user_pwnam = 'some user pwnam'

        getpwnam.side_effect = [existing_user_pwnam, new_user_pwnam]

        result = host.adduser(username, system_user=True)

        self.assertEqual(result, new_user_pwnam)
        check_call.assert_called_with([
            'useradd',
            '--system',
            username
        ])
        getpwnam.assert_called_with(username)

    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_adds_a_user_to_a_group(self, log, check_call):
        username = 'foo'
        group = 'bar'

        host.add_user_to_group(username, group)

        check_call.assert_called_with([
            'gpasswd', '-a',
            username,
            group
        ])

    @patch('grp.getgrnam')
    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_add_a_group_if_it_doesnt_exist(self, log, check_call, getgrnam):
        group_name = 'testgroup'
        existing_group_grnam = KeyError('group not found')
        new_group_grnam = 'some group grnam'

        getgrnam.side_effect = [existing_group_grnam, new_group_grnam]

        result = host.add_group(group_name)

        self.assertEqual(result, new_group_grnam)
        check_call.assert_called_with(['addgroup', '--group', group_name])
        getgrnam.assert_called_with(group_name)

    @patch('grp.getgrnam')
    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_doesnt_add_group_if_it_already_exists(self, log, check_call,
                                                   getgrnam):
        group_name = 'testgroup'
        existing_group_grnam = 'some group grnam'

        getgrnam.return_value = existing_group_grnam

        result = host.add_group(group_name)

        self.assertEqual(result, existing_group_grnam)
        self.assertFalse(check_call.called)
        getgrnam.assert_called_with(group_name)

    @patch('grp.getgrnam')
    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_add_a_system_group(self, log, check_call, getgrnam):
        group_name = 'testgroup'
        existing_group_grnam = KeyError('group not found')
        new_group_grnam = 'some group grnam'

        getgrnam.side_effect = [existing_group_grnam, new_group_grnam]

        result = host.add_group(group_name, system_group=True)

        self.assertEqual(result, new_group_grnam)
        check_call.assert_called_with([
            'addgroup',
            '--system',
            group_name
        ])
        getgrnam.assert_called_with(group_name)

    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_rsyncs_a_path(self, log, check_output):
        from_path = '/from/this/path/foo'
        to_path = '/to/this/path/bar'
        check_output.return_value = b' some output '  # Spaces will be stripped

        result = host.rsync(from_path, to_path)

        self.assertEqual(result, 'some output')
        check_output.assert_called_with(['/usr/bin/rsync', '-r', '--delete',
                                         '--executability',
                                         '/from/this/path/foo',
                                         '/to/this/path/bar'])

    @patch('subprocess.check_call')
    @patch.object(host, 'log')
    def test_creates_a_symlink(self, log, check_call):
        source = '/from/this/path/foo'
        destination = '/to/this/path/bar'

        host.symlink(source, destination)

        check_call.assert_called_with(['ln', '-sf',
                                       '/from/this/path/foo',
                                       '/to/this/path/bar'])

    @patch('pwd.getpwnam')
    @patch('grp.getgrnam')
    @patch.object(host, 'log')
    @patch.object(host, 'os')
    def test_creates_a_directory_if_it_doesnt_exist(self, os_, log,
                                                    getgrnam, getpwnam):
        uid = 123
        gid = 234
        owner = 'some-user'
        group = 'some-group'
        path = '/some/other/path/from/link'
        realpath = '/some/path'
        path_exists = False
        perms = 0o644

        getpwnam.return_value.pw_uid = uid
        getgrnam.return_value.gr_gid = gid
        os_.path.abspath.return_value = realpath
        os_.path.exists.return_value = path_exists

        host.mkdir(path, owner=owner, group=group, perms=perms)

        getpwnam.assert_called_with('some-user')
        getgrnam.assert_called_with('some-group')
        os_.path.abspath.assert_called_with(path)
        os_.path.exists.assert_called_with(realpath)
        os_.makedirs.assert_called_with(realpath, perms)
        os_.chown.assert_called_with(realpath, uid, gid)

    @patch.object(host, 'log')
    @patch.object(host, 'os')
    def test_creates_a_directory_with_defaults(self, os_, log):
        uid = 0
        gid = 0
        path = '/some/other/path/from/link'
        realpath = '/some/path'
        path_exists = False
        perms = 0o555

        os_.path.abspath.return_value = realpath
        os_.path.exists.return_value = path_exists

        host.mkdir(path)

        os_.path.abspath.assert_called_with(path)
        os_.path.exists.assert_called_with(realpath)
        os_.makedirs.assert_called_with(realpath, perms)
        os_.chown.assert_called_with(realpath, uid, gid)

    @patch('pwd.getpwnam')
    @patch('grp.getgrnam')
    @patch.object(host, 'log')
    @patch.object(host, 'os')
    def test_removes_file_with_same_path_before_mkdir(self, os_, log,
                                                      getgrnam, getpwnam):
        uid = 123
        gid = 234
        owner = 'some-user'
        group = 'some-group'
        path = '/some/other/path/from/link'
        realpath = '/some/path'
        path_exists = True
        force = True
        is_dir = False
        perms = 0o644

        getpwnam.return_value.pw_uid = uid
        getgrnam.return_value.gr_gid = gid
        os_.path.abspath.return_value = realpath
        os_.path.exists.return_value = path_exists
        os_.path.isdir.return_value = is_dir

        host.mkdir(path, owner=owner, group=group, perms=perms, force=force)

        getpwnam.assert_called_with('some-user')
        getgrnam.assert_called_with('some-group')
        os_.path.abspath.assert_called_with(path)
        os_.path.exists.assert_called_with(realpath)
        os_.unlink.assert_called_with(realpath)
        os_.makedirs.assert_called()
        os_.chown.assert_called_with(realpath, uid, gid)

    @patch('pwd.getpwnam')
    @patch('grp.getgrnam')
    @patch.object(host, 'log')
    @patch.object(host, 'os')
    def test_writes_content_to_a_file(self, os_, log, getgrnam, getpwnam):
        # Curly brackets here demonstrate that we are *not* rendering
        # these strings with Python's string formatting. This is a
        # change from the original behavior per Bug #1195634.
        uid = 123
        gid = 234
        owner = 'some-user-{foo}'
        group = 'some-group-{bar}'
        path = '/some/path/{baz}'
        contents = b'what is {juju}'
        perms = 0o644
        fileno = 'some-fileno'

        getpwnam.return_value.pw_uid = uid
        getgrnam.return_value.gr_gid = gid

        with patch_open() as (mock_open, mock_file):
            mock_file.fileno.return_value = fileno

            host.write_file(path, contents, owner=owner, group=group,
                            perms=perms)

            getpwnam.assert_called_with('some-user-{foo}')
            getgrnam.assert_called_with('some-group-{bar}')
            mock_open.assert_called_with('/some/path/{baz}', 'wb')
            os_.fchown.assert_called_with(fileno, uid, gid)
            os_.fchmod.assert_called_with(fileno, perms)
            mock_file.write.assert_called_with(b'what is {juju}')

    @patch.object(host, 'log')
    @patch.object(host, 'os')
    def test_writes_content_with_default(self, os_, log):
        uid = 0
        gid = 0
        path = '/some/path/{baz}'
        fmtstr = b'what is {juju}'
        perms = 0o444
        fileno = 'some-fileno'

        with patch_open() as (mock_open, mock_file):
            mock_file.fileno.return_value = fileno

            host.write_file(path, fmtstr)

            mock_open.assert_called_with('/some/path/{baz}', 'wb')
            os_.fchown.assert_called_with(fileno, uid, gid)
            os_.fchmod.assert_called_with(fileno, perms)
            mock_file.write.assert_called_with(b'what is {juju}')

    @patch.object(host, 'log')
    @patch.object(host, 'os')
    def test_writes_binary_contents(self, os_, log):
        path = '/some/path/{baz}'
        fmtstr = six.u('what is {juju}\N{TRADE MARK SIGN}').encode('UTF-8')
        fileno = 'some-fileno'

        with patch_open() as (mock_open, mock_file):
            mock_file.fileno.return_value = fileno

            host.write_file(path, fmtstr)

            mock_open.assert_called_with('/some/path/{baz}', 'wb')
            mock_file.write.assert_called_with(fmtstr)

    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_mounts_a_device(self, log, check_output):
        device = '/dev/guido'
        mountpoint = '/mnt/guido'
        options = 'foo,bar'

        result = host.mount(device, mountpoint, options)

        self.assertTrue(result)
        check_output.assert_called_with(['mount', '-o', 'foo,bar',
                                         '/dev/guido', '/mnt/guido'])

    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_doesnt_mount_on_error(self, log, check_output):
        device = '/dev/guido'
        mountpoint = '/mnt/guido'
        options = 'foo,bar'

        error = subprocess.CalledProcessError(123, 'mount it', 'Oops...')
        check_output.side_effect = error

        result = host.mount(device, mountpoint, options)

        self.assertFalse(result)
        check_output.assert_called_with(['mount', '-o', 'foo,bar',
                                         '/dev/guido', '/mnt/guido'])

    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_mounts_a_device_without_options(self, log, check_output):
        device = '/dev/guido'
        mountpoint = '/mnt/guido'

        result = host.mount(device, mountpoint)

        self.assertTrue(result)
        check_output.assert_called_with(['mount', '/dev/guido', '/mnt/guido'])

    @patch.object(host, 'Fstab')
    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_mounts_and_persist_a_device(self, log, check_output, fstab):
        """Check if a mount works with the persist flag set to True
        """
        device = '/dev/guido'
        mountpoint = '/mnt/guido'
        options = 'foo,bar'

        result = host.mount(device, mountpoint, options, persist=True)

        self.assertTrue(result)
        check_output.assert_called_with(['mount', '-o', 'foo,bar',
                                         '/dev/guido', '/mnt/guido'])

        fstab.add.assert_called_with('/dev/guido', '/mnt/guido', 'ext3',
                                     options='foo,bar')

        result = host.mount(device, mountpoint, options, persist=True,
                            filesystem="xfs")

        self.assertTrue(result)
        fstab.add.assert_called_with('/dev/guido', '/mnt/guido', 'xfs',
                                     options='foo,bar')

    @patch.object(host, 'Fstab')
    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_umounts_a_device(self, log, check_output, fstab):
        mountpoint = '/mnt/guido'

        result = host.umount(mountpoint, persist=True)

        self.assertTrue(result)
        check_output.assert_called_with(['umount', mountpoint])
        fstab.remove_by_mountpoint_called_with(mountpoint)

    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_umounts_and_persist_device(self, log, check_output):
        mountpoint = '/mnt/guido'

        result = host.umount(mountpoint)

        self.assertTrue(result)
        check_output.assert_called_with(['umount', '/mnt/guido'])

    @patch('subprocess.check_output')
    @patch.object(host, 'log')
    def test_doesnt_umount_on_error(self, log, check_output):
        mountpoint = '/mnt/guido'

        error = subprocess.CalledProcessError(123, 'mount it', 'Oops...')
        check_output.side_effect = error

        result = host.umount(mountpoint)

        self.assertFalse(result)
        check_output.assert_called_with(['umount', '/mnt/guido'])

    def test_lists_the_mount_points(self):
        with patch_open() as (mock_open, mock_file):
            mock_file.readlines.return_value = MOUNT_LINES
            result = host.mounts()

            self.assertEqual(result, [
                ['/', 'rootfs'],
                ['/sys', 'sysfs'],
                ['/proc', 'proc'],
                ['/dev', 'udev'],
                ['/dev/pts', 'devpts']
            ])
            mock_open.assert_called_with('/proc/mounts')

    _hash_files = {
        '/etc/exists.conf': 'lots of nice ceph configuration',
        '/etc/missing.conf': None
    }

    @patch('hashlib.md5')
    @patch('os.path.exists')
    def test_file_hash_exists(self, exists, md5):
        filename = '/etc/exists.conf'
        exists.side_effect = [True]
        m = md5()
        m.hexdigest.return_value = self._hash_files[filename]
        with patch_open() as (mock_open, mock_file):
            mock_file.read.return_value = self._hash_files[filename]
            result = host.file_hash(filename)
            self.assertEqual(result, self._hash_files[filename])

    @patch('os.path.exists')
    def test_file_hash_missing(self, exists):
        filename = '/etc/missing.conf'
        exists.side_effect = [False]
        with patch_open() as (mock_open, mock_file):
            mock_file.read.return_value = self._hash_files[filename]
            result = host.file_hash(filename)
            self.assertEqual(result, None)

    @patch('hashlib.sha1')
    @patch('os.path.exists')
    def test_file_hash_sha1(self, exists, sha1):
        filename = '/etc/exists.conf'
        exists.side_effect = [True]
        m = sha1()
        m.hexdigest.return_value = self._hash_files[filename]
        with patch_open() as (mock_open, mock_file):
            mock_file.read.return_value = self._hash_files[filename]
            result = host.file_hash(filename, hash_type='sha1')
            self.assertEqual(result, self._hash_files[filename])

    @patch.object(host, 'file_hash')
    def test_check_hash(self, file_hash):
        file_hash.return_value = 'good-hash'
        self.assertRaises(host.ChecksumError, host.check_hash, 'file', 'bad-hash')
        host.check_hash('file', 'good-hash', 'sha256')
        self.assertEqual(file_hash.call_args_list, [
            call('file', 'md5'),
            call('file', 'sha256'),
        ])

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_restart_no_changes(self, iglob, exists, service):
        file_name = '/etc/missing.conf'
        restart_map = {
            file_name: ['test-service']
        }
        iglob.return_value = []

        @host.restart_on_change(restart_map)
        def make_no_changes():
            pass

        make_no_changes()

        assert not service.called
        assert not exists.called

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_restart_on_change(self, iglob, exists, service):
        file_name = '/etc/missing.conf'
        restart_map = {
            file_name: ['test-service']
        }
        iglob.side_effect = [[], [file_name]]
        exists.return_value = True

        @host.restart_on_change(restart_map)
        def make_some_changes(mock_file):
            mock_file.read.return_value = b"newstuff"

        with patch_open() as (mock_open, mock_file):
            make_some_changes(mock_file)

        for service_name in restart_map[file_name]:
            service.assert_called_with('restart', service_name)

        exists.assert_has_calls([
            call(file_name),
        ])

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_multiservice_restart_on_change(self, iglob, exists, service):
        file_name_one = '/etc/missing.conf'
        file_name_two = '/etc/exists.conf'
        restart_map = {
            file_name_one: ['test-service'],
            file_name_two: ['test-service', 'test-service2']
        }
        iglob.side_effect = [[], [file_name_two],
                             [file_name_one], [file_name_two]]
        exists.return_value = True

        @host.restart_on_change(restart_map)
        def make_some_changes():
            pass

        with patch_open() as (mock_open, mock_file):
            mock_file.read.side_effect = [b'exists', b'missing', b'exists2']
            make_some_changes()

        # Restart should only happen once per service
        for svc in ['test-service2', 'test-service']:
            c = call('restart', svc)
            self.assertEquals(1, service.call_args_list.count(c))

        exists.assert_has_calls([
            call(file_name_one),
            call(file_name_two)
        ])

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_multiservice_restart_on_change_in_order(self, iglob, exists, service):
        file_name_one = '/etc/cinder/cinder.conf'
        file_name_two = '/etc/haproxy/haproxy.conf'
        restart_map = OrderedDict([
            (file_name_one, ['some-api']),
            (file_name_two, ['haproxy'])
        ])
        iglob.side_effect = [[], [file_name_two],
                             [file_name_one], [file_name_two]]
        exists.return_value = True

        @host.restart_on_change(restart_map)
        def make_some_changes():
            pass

        with patch_open() as (mock_open, mock_file):
            mock_file.read.side_effect = [b'exists', b'missing', b'exists2']
            make_some_changes()

        # Restarts should happen in the order they are described in the
        # restart map.
        expected = [
            call('restart', 'some-api'),
            call('restart', 'haproxy')
        ]
        self.assertEquals(expected, service.call_args_list)

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_glob_no_restart(self, iglob, exists, service):
        glob_path = '/etc/service/*.conf'
        file_name_one = '/etc/service/exists.conf'
        file_name_two = '/etc/service/exists2.conf'
        restart_map = {
            glob_path: ['service']
        }
        iglob.side_effect = [[file_name_one, file_name_two],
                             [file_name_one, file_name_two]]
        exists.return_value = True

        @host.restart_on_change(restart_map)
        def make_some_changes():
            pass

        with patch_open() as (mock_open, mock_file):
            mock_file.read.side_effect = [b'content', b'content2',
                                          b'content', b'content2']
            make_some_changes()

        self.assertEquals([], service.call_args_list)

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_glob_restart_on_change(self, iglob, exists, service):
        glob_path = '/etc/service/*.conf'
        file_name_one = '/etc/service/exists.conf'
        file_name_two = '/etc/service/exists2.conf'
        restart_map = {
            glob_path: ['service']
        }
        iglob.side_effect = [[file_name_one, file_name_two],
                             [file_name_one, file_name_two]]
        exists.return_value = True

        @host.restart_on_change(restart_map)
        def make_some_changes():
            pass

        with patch_open() as (mock_open, mock_file):
            mock_file.read.side_effect = [b'content', b'content2',
                                          b'changed', b'content2']
            make_some_changes()

        self.assertEquals([call('restart', 'service')], service.call_args_list)

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_glob_restart_on_create(self, iglob, exists, service):
        glob_path = '/etc/service/*.conf'
        file_name_one = '/etc/service/exists.conf'
        file_name_two = '/etc/service/missing.conf'
        restart_map = {
            glob_path: ['service']
        }
        iglob.side_effect = [[file_name_one],
                             [file_name_one, file_name_two]]
        exists.return_value = True

        @host.restart_on_change(restart_map)
        def make_some_changes():
            pass

        with patch_open() as (mock_open, mock_file):
            mock_file.read.side_effect = [b'exists',
                                          b'exists', b'created']
            make_some_changes()

        self.assertEquals([call('restart', 'service')], service.call_args_list)

    @patch.object(host, 'service')
    @patch('os.path.exists')
    @patch('glob.iglob')
    def test_glob_restart_on_delete(self, iglob, exists, service):
        glob_path = '/etc/service/*.conf'
        file_name_one = '/etc/service/exists.conf'
        file_name_two = '/etc/service/exists2.conf'
        restart_map = {
            glob_path: ['service']
        }
        iglob.side_effect = [[file_name_one, file_name_two],
                             [file_name_two]]
        exists.return_value = True

        @host.restart_on_change(restart_map)
        def make_some_changes():
            pass

        with patch_open() as (mock_open, mock_file):
            mock_file.read.side_effect = [b'exists', b'exists2',
                                          b'exists2']
            make_some_changes()

        self.assertEquals([call('restart', 'service')], service.call_args_list)

    def test_lsb_release(self):
        result = {
            "DISTRIB_ID": "Ubuntu",
            "DISTRIB_RELEASE": "13.10",
            "DISTRIB_CODENAME": "saucy",
            "DISTRIB_DESCRIPTION": "\"Ubuntu Saucy Salamander "
                                   "(development branch)\""
        }
        with mocked_open('/etc/lsb-release', LSB_RELEASE):
            lsb_release = host.lsb_release()
            for key in result:
                self.assertEqual(result[key], lsb_release[key])

    def test_pwgen(self):
        pw = host.pwgen()
        self.assert_(len(pw) >= 35, 'Password is too short')

        pw = host.pwgen(10)
        self.assertEqual(len(pw), 10, 'Password incorrect length')

        pw2 = host.pwgen(10)
        self.assertNotEqual(pw, pw2, 'Duplicated password')

    @patch('subprocess.check_output')
    def test_list_nics(self, check_output):
        check_output.return_value = IP_LINES
        nics = host.list_nics('eth')
        self.assertEqual(nics, ['eth0', 'eth1', 'eth0.10'])
        nics = host.list_nics(['eth'])
        self.assertEqual(nics, ['eth0', 'eth1', 'eth0.10'])

    @patch('subprocess.check_output')
    def test_list_nics_with_bonds(self, check_output):
        check_output.return_value = IP_LINE_BONDS
        nics = host.list_nics('bond')
        self.assertEqual(nics, ['bond0.10', ])

    @patch('subprocess.check_output')
    def test_get_nic_mtu_with_bonds(self, check_output):
        check_output.return_value = IP_LINE_BONDS
        nic = "bond0.10"
        mtu = host.get_nic_mtu(nic)
        self.assertEqual(mtu, '1500')

    @patch('subprocess.check_call')
    def test_set_nic_mtu(self, mock_call):
        mock_call.return_value = 0
        nic = 'eth7'
        mtu = '1546'
        host.set_nic_mtu(nic, mtu)
        mock_call.assert_called_with(['ip', 'link', 'set', nic, 'mtu', mtu])

    @patch('subprocess.check_output')
    def test_get_nic_mtu(self, check_output):
        check_output.return_value = IP_LINE_ETH0
        nic = "eth0"
        mtu = host.get_nic_mtu(nic)
        self.assertEqual(mtu, '1500')

    @patch('subprocess.check_output')
    def test_get_nic_mtu_vlan(self, check_output):
        check_output.return_value = IP_LINE_ETH0_VLAN
        nic = "eth0.10"
        mtu = host.get_nic_mtu(nic)
        self.assertEqual(mtu, '1500')

    @patch('subprocess.check_output')
    def test_get_nic_hwaddr(self, check_output):
        check_output.return_value = IP_LINE_HWADDR
        nic = "eth0"
        hwaddr = host.get_nic_hwaddr(nic)
        self.assertEqual(hwaddr, 'e4:11:5b:ab:a7:3c')

    @patch.object(apt_pkg, 'Cache')
    def test_cmp_pkgrevno_revnos(self, pkg_cache):
        class MockPackage:
            class MockPackageRevno:
                def __init__(self, ver_str):
                    self.ver_str = ver_str

            def __init__(self, current_ver):
                self.current_ver = self.MockPackageRevno(current_ver)

        pkg_dict = {
            'python': MockPackage('2.4')
        }
        pkg_cache.return_value = pkg_dict
        self.assertEqual(host.cmp_pkgrevno('python', '2.3'), 1)
        self.assertEqual(host.cmp_pkgrevno('python', '2.4'), 0)
        self.assertEqual(host.cmp_pkgrevno('python', '2.5'), -1)
