##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Windows File Systems

Models file systems by querying Win32_LogicalDisk via WMI.
'''

import re

from ZenPacks.zenoss.Microsoft.Windows.modeler.WinRMPlugin import WinRMPlugin


class FileSystems(WinRMPlugin):
    compname = 'os'
    relname = 'filesystems'
    modname = 'ZenPacks.zenoss.Microsoft.Windows.FileSystem'

    deviceProperties = WinRMPlugin.deviceProperties + (
        'zFileSystemMapIgnoreNames',
        'zFileSystemMapIgnoreTypes',
        )

    queries = {
        'Win32_LogicalDisk': "SELECT * FROM Win32_LogicalDisk",

        # TODO: Do we need to support these too?
        # 'Win32_MappedLogicalDisk': "SELECT * FROM Win32_MappedLogicalDisk",
        # 'Win32_Volume': "SELECT * FROM Win32_Volume",
        }

    custom_powershell_commands = {
        'TotalFiles': "(Get-ChildItem -Path %s -Recurse -Force).Count",
    }

    def process(self, device, results, log):
        log.info(
            "Modeler %s processing data for device %s",
            self.name(), device.id)

        ignore_names = getattr(device, 'zFileSystemMapIgnoreNames', None)
        if ignore_names:
            ignore_names_search = re.compile(ignore_names).search

        ignore_types = getattr(device, 'zFileSystemMapIgnoreTypes', None)

        rm = self.relMap()

        for disk in results.get('Win32_LogicalDisk', ()):
            mount = win32_logicaldisk_mount(disk)

            if ignore_names and ignore_names_search(mount):
                log.info(
                    "Ignoring %s on %s because it matches "
                    "zFileSystemMapIgnoreNames",
                    mount, device.id)

                continue

            if ignore_types:
                zentypes = set(lookup_zendrivetypes(disk.DriveType or -1))
                if zentypes.intersection(ignore_types):
                    log.info(
                        "Ignoring %s on %s because it matches "
                        "zFileSystemMapIgnoreTypes",
                        mount, device.id)

                    continue

            if not disk.BlockSize:
                disk.BlockSize = guess_block_size(disk.Size)

            perfmonInstance = '\\LogicalDisk({})'.format(
                disk.Name.rstrip('\\'))

            total_files = 0
            if results.get(disk.Name, ()):
                total_files = results.get(disk.Name, 0).stdout

            rm.append(self.objectMap({
                'id': self.prepId(disk.DeviceID),
                'title': mount,
                'mount': mount,
                'storageDevice': disk.Name,
                'drivetype': lookup_drivetype(disk.DriveType or -1),
                'mediatype': lookup_mediatype(disk.MediaType or -1),
                'type': disk.FileSystem,
                'blockSize': int(disk.BlockSize),
                'totalBlocks': int(disk.Size) / int(disk.BlockSize),
                'maxNameLen': disk.MaximumComponentLength,
                'perfmonInstance': perfmonInstance,
                'totalFiles': total_files or 0,
                }))

        return rm


def win32_logicaldisk_mount(disk):
    '''
    Return a FileSystem.mount property given a Win32_LogicalDisk.
    '''
    mount_parts = []
    if disk.Name:
        mount_parts.append(disk.Name)

    if disk.VolumeSerialNumber:
        mount_parts.append(
            '(Serial Number: {})'.format(disk.VolumeSerialNumber))

    if disk.VolumeName:
        mount_parts.append(
            '- {}'.format(disk.VolumeName))

    return ' '.join(mount_parts)


def lookup_drivetype(value):
    '''
    Return string representation of Win32_LogicalDisk.Type.
    '''
    return {
        0: 'unknown',
        1: 'no root directory',
        2: 'removable disk',
        3: 'local disk',
        4: 'network drive',
        5: 'CD',
        6: 'RAM disk',
        }.get(int(value), 'unknown')


def lookup_mediatype(value):
    '''
    Return string representation of Win32_LogicalDisk.MediaType.
    '''
    return {
        0: 'Format is unknown',
        1: '5 1/4-Inch Floppy Disk - 1.2 MB - 512 bytes/sector',
        2: '3 1/2-Inch Floppy Disk - 1.44 MB -512 bytes/sector',
        3: '3 1/2-Inch Floppy Disk - 2.88 MB - 512 bytes/sector',
        4: '3 1/2-Inch Floppy Disk - 20.8 MB - 512 bytes/sector',
        5: '3 1/2-Inch Floppy Disk - 720 KB - 512 bytes/sector',
        6: '5 1/4-Inch Floppy Disk - 360 KB - 512 bytes/sector',
        7: '5 1/4-Inch Floppy Disk - 320 KB - 512 bytes/sector',
        8: '5 1/4-Inch Floppy Disk - 320 KB - 1024 bytes/sector',
        9: '5 1/4-Inch Floppy Disk - 180 KB - 512 bytes/sector',
        10: '5 1/4-Inch Floppy Disk - 160 KB - 512 bytes/sector',
        11: 'Removable media other than floppy',
        12: 'Fixed hard disk media',
        13: '3 1/2-Inch Floppy Disk - 120 MB - 512 bytes/sector',
        14: '3 1/2-Inch Floppy Disk - 640 KB - 512 bytes/sector',
        15: '5 1/4-Inch Floppy Disk - 640 KB - 512 bytes/sector',
        16: '5 1/4-Inch Floppy Disk - 720 KB - 512 bytes/sector',
        17: '3 1/2-Inch Floppy Disk - 1.2 MB - 512 bytes/sector',
        18: '3 1/2-Inch Floppy Disk - 1.23 MB - 1024 bytes/sector',
        19: '5 1/4-Inch Floppy Disk - 1.23 MB - 1024 bytes/sector',
        20: '3 1/2-Inch Floppy Disk - 128 MB - 512 bytes/sector',
        21: '3 1/2-Inch Floppy Disk - 230 MB - 512 bytes/sector',
        22: '8-Inch Floppy Disk - 256 KB - 128 bytes/sector',
        }.get(int(value), 'unknown')


def lookup_zendrivetypes(value):
    '''
    Return a list of file system types for Win32_LogicalDisk.Type.
    '''
    return {
        0: ['other'],
        2: ['removableDisk', 'floppyDisk'],
        3: ['fixedDisk'],
        4: ['networkDisk'],
        5: ['compactDisk'],
        6: ['ramDisk', 'virtualMemory', 'ram', 'flashMemory'],
        }.get(int(value), ['unknown'])


def guess_block_size(bytes):
    '''
    Return a best guess at block size given bytes.

    Most of the MS operating systems don't seem to return a value for
    block size.  So, let's try to guess by how the size is rounded off.
    That is, if the number is divisible by 1024, that's probably due to
    the block size. Ya, it's a kludge.
    '''
    for i in range(10, 17):
        if int(bytes) / float(1 << i) % 1:
            return 1 << (i - 1)

    # Naive assumption. Though so far it seems to work.
    return 4096
