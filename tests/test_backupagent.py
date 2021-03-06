"""Unit tests for backupagent."""
import json
import unittest
from mock import patch
from azfilebak import backupconfiguration
from azfilebak import backupagent
from azfilebak.azurevminstancemetadata import AzureVMInstanceMetadata
from azfilebak.businesshours import BusinessHours
from azfilebak.scheduleparser import ScheduleParser
from azfilebak.naming import Naming
from tests.loggedtestcase import LoggedTestCase

class TestBackupAgent(LoggedTestCase):
    """Unit tests for class BackupAgent."""

    def setUp(self):
        self.json_meta = open('sample_instance_metadata.json').read()

        self.meta = AzureVMInstanceMetadata(
            lambda: (json.JSONDecoder()).decode(self.json_meta)
        )

        self.patcher1 = patch('azfilebak.azurevminstancemetadata.AzureVMInstanceMetadata.create_instance',
                              return_value=self.meta)
        self.patcher1.start()

        self.cfg = backupconfiguration.BackupConfiguration(config_filename="sample_backup.conf")
        self.agent = backupagent.BackupAgent(self.cfg)

    def test_should_run_full_backup(self):
        """Test should_run_full_backup"""
        sample_data = (
            "bkp_fs_schedule:"
            "mo:111111 111000 000000 011111, "
            "tu:111111 111000 000000 011111, "
            "we:111111 111000 000000 011111, "
            "th:111111 111000 000000 011111, "
            "fr:111111 111000 000000 011111, "
            "sa:111111 111111 111111 111111, "
            "su:111111 111111 111111 111111, "
            "min:1d, "
            "max:3d"
        )

        business_hours = BusinessHours.parse_tag_str(sample_data)
        db_backup_interval_min = ScheduleParser.parse_timedelta("24h")
        db_backup_interval_max = ScheduleParser.parse_timedelta("3d")
        five_day_backup = "20180601_010000"
        two_day_backup = "20180604_010000"
        same_day_backup = "20180606_010000"
        during_business_hours = "20180606_150000"
        outside_business_hours = "20180606_220000"

        # Forced
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=during_business_hours, force=True,
            latest_full_backup_timestamp=same_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # Forced
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=during_business_hours, force=True,
            latest_full_backup_timestamp=two_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # Forced
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=during_business_hours, force=True,
            latest_full_backup_timestamp=five_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # respecting business hours, and not needed anyway
        self.assertFalse(self.agent.should_run_full_backup(
            now_time=during_business_hours, force=False,
            latest_full_backup_timestamp=same_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # respecting business hours
        self.assertFalse(self.agent.should_run_full_backup(
            now_time=during_business_hours, force=False,
            latest_full_backup_timestamp=two_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # a really old backup, so we ignore business hours
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=during_business_hours, force=False,
            latest_full_backup_timestamp=five_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # outside_business_hours, but same_day_backup, so no backup
        self.assertFalse(self.agent.should_run_full_backup(
            now_time=outside_business_hours, force=False,
            latest_full_backup_timestamp=same_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # outside_business_hours and need to backup
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=outside_business_hours, force=False,
            latest_full_backup_timestamp=two_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # a really old backup
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=outside_business_hours, force=False,
            latest_full_backup_timestamp=five_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # Forced
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=outside_business_hours, force=True,
            latest_full_backup_timestamp=same_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # Forced
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=outside_business_hours, force=True,
            latest_full_backup_timestamp=two_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))
        # Forced
        self.assertTrue(self.agent.should_run_full_backup(
            now_time=outside_business_hours, force=True,
            latest_full_backup_timestamp=five_day_backup,
            business_hours=business_hours,
            db_backup_interval_min=db_backup_interval_min,
            db_backup_interval_max=db_backup_interval_max))

    def test_backup_single_fileset(self):
        """Test backup single fileset."""
        # Force a full backup
        blob = self.agent.backup_single_fileset('tmp_dir', True, True)
        # Check the blob exists
        container = self.cfg.azure_storage_container_name
        self.assertTrue(self.cfg.storage_client.exists(container, blob))

    def test_existing_backups(self):
        """Test list of existing backups."""
        # This test assumes that there are some existing backups for tmp_dir
        # and for no other fileset.
        backups_one = self.agent.existing_backups(['tmp_dir'])
        self.assertGreater(len(backups_one), 0)
        backups_all = self.agent.existing_backups([])
        self.assertGreater(len(backups_all), 0)
        # Non-existing fileset
        backups_none = self.agent.existing_backups(['XXX'])
        self.assertEquals(len(backups_none), 0)

    def test_list_backups(self):
        """Test list of existing backups."""
        # This test assumes that there are some existing backups for tmp_dir
        # and for no other fileset.
        self.agent.list_backups(['tmp_dir'])
        self.agent.list_backups([])
        # Non-existing fileset
        self.agent.list_backups(['XXX'])
        return True

    def test_restore_single_fileset(self):
        """Test restoring a single fileset."""
        # We should have a backup from the preceding test cases.
        backups = self.agent.existing_backups_for_fileset('tmp_dir', True)
        blob_name = backups.popitem()[1][0]
        (fileset, _is_full, timestamp) = Naming.parse_blobname(blob_name)
        self.agent.restore_single_fileset(fileset, timestamp, '/tmp')
        # TODO: test that expected files were indeed restored...
        return True

    def test_prune_old_backups(self):
        """Test prune_old_backups."""
        # Delete backups older than 7 days
        age = age = ScheduleParser.parse_timedelta('8d')
        self.agent.prune_old_backups(age, ['tmp_dir'])
        # TODO: test the backup was effectively deleted
        return True

    def test_show_configuration(self):
        """Test show_configuration."""
        conf = self.agent.show_configuration('/tmp')
        print conf
        return True

    def test_backup_default(self):
        """Test backup_default."""
        self.agent.backup_default(True, True)
        return True

    def tearDown(self):
        self.patcher1.stop()

if __name__ == '__main__':
    unittest.main()
