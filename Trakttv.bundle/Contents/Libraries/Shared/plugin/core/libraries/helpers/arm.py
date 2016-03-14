from plugin.core.helpers.variable import try_convert

import logging
import os

log = logging.getLogger(__name__)


class ArmHelper(object):
    _cpuinfo_cache = None
    _cpuinfo_lines = None

    @classmethod
    def attributes(cls, force_refresh=False):
        if not force_refresh and cls._cpuinfo_cache is not None:
            return cls._cpuinfo_cache

        # Retrieve data from "/proc/cpuinfo"
        lines = cls._fetch(force_refresh)

        if lines:
            # Parse lines
            cls._cpuinfo_cache = cls._parse(lines)
        else:
            # Clear cache
            cls._cpuinfo_cache = None

        return cls._cpuinfo_cache or (None, None)

    @classmethod
    def identifier(cls, force_refresh=False):
        # Retrieve CPU information
        processors, extra = cls.attributes(force_refresh)

        # Lookup CPU in table
        return cls.lookup(processors, extra)

    @classmethod
    def lookup(cls, processors, extra):
        if not processors or 0 not in processors:
            log.info('No valid processors returned from "/proc/cpuinfo"')
            return None, None, None

        # Retrieve processor attributes
        cpu = processors[0]

        cpu_implementer = cls._cast_hex(cpu.get('cpu_implementer'))
        cpu_part = cls._cast_hex(cpu.get('cpu_part'))

        if not cpu_implementer or not cpu_part:
            return None, None, None

        # Try map CPU to a known name
        identifier = CPU_TABLE.get((cpu_implementer, cpu_part))

        if identifier is None:
            log.warn('Unknown CPU - implementer: 0x%X, part: 0x%X, hardware: %r' % (cpu_implementer, cpu_part, extra.get('hardware')))
            return None, None, None

        if len(identifier) < 3:
            # Pad identifier with `None` values
            identifier = tuple(list(identifier) + [None for x in xrange(3 - len(identifier))])

        if len(identifier) > 3:
            log.warn('Invalid identifier format returned: %r', identifier)
            return None, None, None

        return identifier

    @classmethod
    def _cast_hex(cls, value):
        if not value:
            return None

        try:
            return int(value, 0)
        except Exception:
            log.warn('Unable to cast %r to an integer', value, exc_info=True)
            return None

    @classmethod
    def _fetch(cls, force_refresh=False):
        if not force_refresh and cls._cpuinfo_lines is not None:
            return cls._cpuinfo_lines

        # Ensure cpuinfo is available
        if not os.path.exists('/proc/cpuinfo'):
            log.info('Unable to retrieve information from "/proc/cpuinfo", path doesn\'t exist')
            return None

        # Fetch cpuinfo from procfs
        log.debug('Fetching processor information from "/proc/cpuinfo"...')

        with open('/proc/cpuinfo') as fp:
            data = fp.read()

        # Split `data` into lines
        if data:
            cls._cpuinfo_lines = data.split('\n')
        else:
            cls._cpuinfo_lines = None

        # Return lines
        return cls._cpuinfo_lines

    @classmethod
    def _parse(cls, lines):
        processors = {}
        extra = {}

        # Parse lines into `processors` and `extra`
        section = None
        current = {}

        for line in lines:
            # Handle section break
            if line == '':
                # Store current attributes
                if section == 'processor':
                    num = try_convert(current.pop('processor', None), int)

                    if num is None:
                        num = len(processors)

                    processors[num] = current
                elif section == 'extra':
                    extra.update(current)
                elif current:
                    log.debug('Discarding unknown attributes: %r', current)

                # Reset state
                section = None
                current = {}

                # Continue with next line
                continue

            # Parse attribute from line
            parts = [part.strip() for part in line.split(':', 1)]

            if len(parts) < 2:
                log.debug('Unable to parse attribute from line: %r', line)
                continue

            # Retrieve attribute components
            key, value = parts[0], parts[1]

            if not key:
                log.debug('Invalid key returned for line: %r', line)
                continue

            # Transform `key`
            key = key.lower()
            key = key.replace(' ', '_')

            # Check for section-identifier
            if not section:
                if key == 'processor':
                    section = 'processor'
                else:
                    section = 'extra'

            # Store attribute in current dictionary
            current[key] = value

        # Store any leftover extra attributes
        if section == 'extra' and current:
            extra.update(current)

        # Return result
        return processors, extra


CPU_TABLE = {
    # Format: (<implementer>, <part>): (<vendor>, <name>[, <type>])

    # ARM
    (0x41, 0xB02): ('arm', '11-MPCore'),
    (0x41, 0xB36): ('arm', '1136'),
    (0x41, 0xB56): ('arm', '1156'),
    (0x41, 0xB76): ('arm', '1176'),                                 # (Raspberry Pi 1)

    # Marvell
    (0x56, 0x581): ('marvell', 'armada-370/XP', 'marvell-pj4'),     # (DS213j)
    (0x56, 0x584): ('marvell', 'armada-370/XP', 'marvell-pj4'),     # (DS114, DS115j, DS214se, DS216se, DS414slim, RS214)
    (0x41, 0xC09): ('marvell', 'armada-375',    'marvell-pj4')      # (DS215j)
}
