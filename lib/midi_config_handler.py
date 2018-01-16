# -*- coding: utf-8 -*-
#********************************************************************
# ZYNTHIAN PROJECT: Zynthian Web Configurator
#
# MIDI Configuration Handler
#
# Copyright (C) 2017 Markus Heidt <markus@heidt-tech.com>
#
#********************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
#********************************************************************

import os
import sys
import tornado.web
import logging
import re
from collections import OrderedDict
from subprocess import check_output
from lib.ZynthianConfigHandler import ZynthianConfigHandler
import jack
sys.path.append(os.environ.get('ZYNTHIAN_UI_DIR'))
from zyngine.zynthian_midi_filter import MidiFilterScript

#------------------------------------------------------------------------------
# System Menu
#------------------------------------------------------------------------------

class MidiConfigHandler(ZynthianConfigHandler):
	PROFILES_DIRECTORY = os.environ.get("ZYNTHIAN_MY_DATA_DIR")+"/midi-profiles"

	midi_program_change_presets=OrderedDict([
		['Custom', {
			'ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP': '',
			'ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN': '',
			'ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP': '',
			'ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN': ''
		}],
		['Roland', {
			'ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP': 'C#7F',
			'ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN': 'C#00',
			'ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP': 'B#007F',
			'ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN': 'B#0000'
		}]
	])

	program_change_mode_labels=OrderedDict([
		['32', 'LSB'],
		['0', 'MSB']
	])

	midi_cc_labels=OrderedDict([
		['0', '0 - Bank Select (MSB)'],
		['1', '1 - Modulation Wheel (MSB)'],
		['2', '2 - Breath controller (MSB)'],
		['4', '4 - Foot Pedal (MSB)'],
		['5', '5 - Portamento Time (MSB)'],
		['6', '6 - Data Entry (MSB)'],
		['7', '7 - Volume (MSB)'],
		['8', '8 - Balance (MSB)'],
		['10', '10 - Pan Position (MSB)'],
		['11', '11 - Expression (MSB)'],
		['12', '12 - Effect Controller 1 (MSB)'],
		['13', '13 - Effect Controller 2 (MSB)'],

		['32', '32 - Bank Select (LSB)'],
		['33', '33 - Modulation Wheel (LSB)'],
		['34', '34 - Breath controller (LSB)'],
		['36', '36 - Foot Pedal (LSB)'],
		['37', '37 - Portamento Time (LSB)'],
		['38', '38 - Data Entry (LSB)'],
		['39', '39 - Volume (LSB)'],
		['40', '40 - Balance (LSB)'],
		['42', '42 - Pan Position (LSB)'],
		['43', '43 - Expression (LSB)'],
		['44', '44 - Effect Controller 1 (LSB)'],
		['45', '45 - Effect Controller 2 (LSB)'],

		['64', '64 - Sustain Pedal On/Off'],
		['65', '65 - Portamento On/Off'],
		['66', '66 - Sostenuto On/Off'],
		['67', '67 - Soft Pedal On/Off'],
		['68', '68 - Legato On/Off'],

		['71', '71 - VCF Resonance'],
		['72', '72 - VCA Release'],
		['73', '73 - Attack'],
		['74', '74 - VCF Cutoff Freq'],

		['84', '84 - Portamento Amount'],

		['96', '96 - Data Increment'],
		['97', '97 - Data Decrement'],
		['98', '98 - NRPN number (LSB)'],
		['99', '99 - NRPN number (MSB)'],
		['100', '100 - RPN number (LSB)'],
		['101', '101 - RPN number (MSB)'],

		['120', '120 - All Sound Off'],
		['121', '121 - Reset All Controllers'],
		['122', '122 - Local On/Off Switch'],
		['123', '123 - All Notes Off'],
		['124', '124 - Omni Mode Off'],
		['125', '125 - Omni Mode On'],
		['126', '126 - Mono Mode'],
		['127', '127 - Poly Mode']
	])

	midi_event_options=OrderedDict([
		['PG', 'Program change'],
		['KP', 'Polyphonic Key Pressure (Aftertouch)'],
		['CP', 'Channel Pressure (Aftertouch)'],
		['PB', 'Pitch Bending'],
		['CC', 'Continuous Controller Change']
	])

	midi_profile_presets=OrderedDict([])


	def prepare(self):
		super(MidiConfigHandler,self).prepare()
		self.load_midi_profile_directories()


	@tornado.web.authenticated
	def get(self, errors=None):
		self.load_midi_profiles()
		if self.current_midi_profile_script:
			self.midi_envs = self.midi_profile_presets[self.current_midi_profile_script]
		else:
			self.midi_envs = {}
		ports_config=self.get_ports_config()

		add_panel_config=OrderedDict([
			['FILTER_ADD_MIDI_EVENT', {
				'options': list(self.midi_event_options.keys()),
				'option_labels': self.midi_event_options
			}],
			['FILTER_ADD_MAPPED_MIDI_EVENT', {
				'options': list(self.midi_event_options.keys()),
				'option_labels': self.midi_event_options
			}],
			['FILTER_ADD_CC_VALUE', {
				'option_labels': self.midi_cc_labels
			}],
			['FILTER_ADD_MAPPED_CC_VALUE', {
				'option_labels': self.midi_cc_labels
			}]
		])

		#upper case ZYNTHIAN_MIDI will be stored in profile file
		#other upper case in zynthian_envar
		config=OrderedDict([
			['ZYNTHIAN_SCRIPT_MIDI_PROFILE', {
				'type': 'select',
				'title': 'MIDI profile',
				'value': self.current_midi_profile_script,
				'options': self.midi_profile_scripts,
				'option_labels': {script_name: os.path.basename(script_name).split('.')[0] for script_name  in self.midi_profile_scripts},
				'presets': self.midi_profile_presets
			}],
			['zynthian_midi_profile_delete_script', {
				'type': 'button',
				'title': 'Delete MIDI profile',
				'button_type': 'submit',
				'class': 'btn-danger',
				'script_file': 'midi_profile_delete.js'
			}],
			['zynthian_midi_profile_new_script_name', {
				'type': 'text',
				'title': 'New MIDI profile',
				'value': ''
			}],
			['zynthian_midi_profile_new_script', {
				'type': 'button',
				'title': 'New MIDI profile',
				'button_type': 'button',
				'class': 'btn-success',
				'script_file': 'midi_profile_new.js'
			}],
			['ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON', {
				'type': 'boolean',
				'title': 'Preset preload on Note-On',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON')
			}],
			['ZYNTHIAN_MIDI_FINE_TUNING', {
				'type': 'select',
				'title': 'MIDI fine tuning (Hz)',
				'value':  self.get_midi_env('ZYNTHIAN_MIDI_FINE_TUNING'),
				'options': map(lambda x: str(x).zfill(2), list(range(392, 493)))
			}],
			['ZYNTHIAN_MIDI_MASTER_CHANNEL', {
				'type': 'select',
				'title': 'Master MIDI channel',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_MASTER_CHANNEL'),
				'options': map(lambda x: str(x).zfill(2), list(range(1, 17)))
			}],
			['ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM', {
				'type': 'select',
				'title': 'Master Bank change mode',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_CCNUM'),
				'options': list(self.program_change_mode_labels.keys()),
				'option_labels': self.program_change_mode_labels,
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_TYPE', {
				'type': 'select',
				'title': 'Master change type',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_TYPE'),
				'options': list(self.midi_program_change_presets.keys()),
				'presets': self.midi_program_change_presets
			}],
			['ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP', {
				'type': 'text',
				'title': 'Master Program change-up',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_UP'),
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN', {
				'type': 'text',
				'title': 'Master Program change-down',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_MASTER_PROGRAM_CHANGE_DOWN'),
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP', {
				'type': 'text',
				'title': 'Master Bank change-up',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_UP'),
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN', {
				'type': 'text',
				'title': 'Master Bank change-down',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_MASTER_BANK_CHANGE_DOWN'),
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_NETWORK_ENABLED', {
				'type': 'boolean',
				'title': 'MIDI network enabled',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_NETWORK_ENABLED'),
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_NETWORK_IN_CHANNEL', {
				'type': 'select',
				'title': 'Network IN channel',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_NETWORK_IN_CHANNEL', '02'),
				'options': map(lambda x: str(x).zfill(2), list(range(1, 17))),
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_NETWORK_OUT_CHANNEL', {
				'type': 'select',
				'title': 'Network OUT channel',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_NETWORK_OUT_CHANNEL','02'),
				'options': map(lambda x: str(x).zfill(2), list(range(1, 17))),
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_FILTER_RULES', {
				'type': 'textarea',
				'title': 'Midi filter rules',
				'value': self.get_midi_env('ZYNTHIAN_MIDI_FILTER_RULES'),
				'cols': 50,
				'rows': 5,
				'addButton': 'display_midi_filter_rule_panel',
				'addPanel': 'midi_filter_rule.html',
				'addPanelConfig': add_panel_config,
				'advanced': True
			}],
			['ZYNTHIAN_MIDI_PORTS', {
				'type': 'textarea',
				'title': 'MIDI Ports',
				'value':self.get_midi_env('ZYNTHIAN_MIDI_PORTS'),
				'cols': 50,
				'rows': 2,
				'addButton': 'display_midi_ports_panel',
				'addPanel': 'midi_ports.html',
				'addPanelConfig': ports_config,
				'advanced': True
			}]
		])

		if self.genjson:
			self.write(config)
		else:
			self.render("config.html", body="config_block.html", config=config, title="MIDI", errors=errors)

	def post(self):
		self.request.arguments['ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON'] = self.request.arguments.get('ZYNTHIAN_MIDI_PRESET_PRELOAD_NOTEON','0')
		self.request.arguments['ZYNTHIAN_MIDI_NETWORK_ENABLED'] = self.request.arguments.get('ZYNTHIAN_MIDI_NETWORK_ENABLED','0')

		escaped_request_arguments = tornado.escape.recursive_unicode(self.request.arguments)

		filter_error = self.validate_filter_rules(escaped_request_arguments);
		errors = {}
		if not filter_error:
			# remove fields that sttart with FILTER_ADD from request_args, so that they won't be passed to update_config
			for filter_add_argument in list(escaped_request_arguments.keys()):
				if filter_add_argument.startswith('FILTER_ADD'):
					del escaped_request_arguments[filter_add_argument]

			new_profile_script_name = self.get_argument('zynthian_midi_profile_new_script_name')

			if new_profile_script_name:
				#New MIDI profile
				new_profile_script_path = self.PROFILE_USER_DIRECTORY + '/' + new_profile_script_name + '.sh'
				self.update_profile(new_profile_script_path, escaped_request_arguments)
				mode = os.stat(new_profile_script_path).st_mode
				mode |= (mode & 0o444) >> 2	# copy R bits to X
				os.chmod(new_profile_script_path, mode)
				self.load_midi_profile_directories()
			elif 'zynthian_midi_profile_delete_script' in self.request.arguments and self.get_argument('zynthian_midi_profile_delete_script') == "1":
				#DELETE
				if self.current_midi_profile_script.startswith(self.PROFILE_USER_DIRECTORY):
					os.remove(self.current_midi_profile_script)
				else:
					errors['zynthian_midi_profile_delete_script'] = 'You can only delete user profiles!'
			else:
				#SAVE
				if self.current_midi_profile_script:
					updateParameters = []
					for parameter in escaped_request_arguments:
						if not parameter.startswith('ZYNTHIAN_'):
							updateParameters.append(parameter)

					for k in updateParameters:
						del escaped_request_arguments[k]

					self.update_profile(self.current_midi_profile_script, escaped_request_arguments)
					errors = self.update_config(escaped_request_arguments)
				else:
					errors['zynthian_midi_profile_new_script_name'] = 'Profile name missing'
			self.restart_ui()
		else:
			errors = {'ZYNTHIAN_MIDI_FILTER_RULES':filter_error};
		self.get(errors)


	def load_midi_profile_directories(self):
		#Get profiles list
		self.midi_profile_scripts = [self.PROFILES_DIRECTORY + '/' + x for x in os.listdir(self.PROFILES_DIRECTORY)]
		#Get active profile
		self.current_midi_profile_script=None
		if 'ZYNTHIAN_SCRIPT_MIDI_PROFILE' in self.request.arguments:
			self.current_midi_profile_script = self.get_argument('ZYNTHIAN_SCRIPT_MIDI_PROFILE')
		else:
			self.current_midi_profile_script = os.getenv('ZYNTHIAN_SCRIPT_MIDI_PROFILE',self.midi_profile_scripts[0])
		if self.current_midi_profile_script not in self.midi_profile_scripts:
			#Create empty default profile
			self.current_midi_profile_script = self.PROFILES_DIRECTORY + "/default.sh"
			self.midi_profile_scripts=[self.current_midi_profile_script]
			self.update_profile(self.current_midi_profile_script, {})

	def validate_filter_rules(self, escaped_request_arguments):
		if escaped_request_arguments['ZYNTHIAN_MIDI_FILTER_RULES'][0]:
			newLine = escaped_request_arguments['ZYNTHIAN_MIDI_FILTER_RULES'][0];
			try:
				mfs = MidiFilterScript(newLine, False)
			except Exception as e:
				return "ERROR parsing MIDI filter rule: " + str(e)

	def get_ports_config(self):
		midi_ports = []
		try:
			client = jack.Client("ZynthianWebConf")
			midi_in_ports = client.get_ports( is_midi=True, is_physical=True, is_input=True)
			midi_out_ports = client.get_ports( is_midi=True, is_physical=True, is_output=True)
			#midi_in_ports = client.get_ports( is_physical=True, is_output=True)
			#midi_out_ports = client.get_ports( is_physical=True, is_input=True)

			current_midi_ports = os.getenv('ZYNTHIAN_MIDI_PORTS','')
			#logging.info(current_midi_ports)

			for idx,midi_port in enumerate(midi_in_ports):
				midi_ports.append({
					'midi_in':midi_port.shortname,
					'midi_out':midi_out_ports[idx].shortname,
					'checked_in': 'checked="checked"' if midi_port.shortname in current_midi_ports else '',
					'checked_out': 'checked="checked"' if midi_out_ports[idx].shortname in current_midi_ports else ''})

		except Exception as e:
			logging.error(e)

		ports_config=OrderedDict([
			['MIDI_PORTS', midi_ports]
		])
		return ports_config
		#logging.info(str(ports_config))


	def load_midi_profiles(self):
		p = re.compile("export (\w*)=\"(.*)\"")
		invalidFiles = []
		for midi_profile_script in self.midi_profile_scripts:
			#logging.info(midi_profile_script)
			profile_values = {}
			try:
				with open(midi_profile_script) as f:
					for line in f:
						m = p.match(line)
						if m:
							profile_values[m.group(1)] = m.group(2)
				self.midi_profile_presets[midi_profile_script] = profile_values
			except:
				invalidFiles.append(midi_profile_script)

		for midi_profile_script in invalidFiles:
			logging.info("invalid file will be ignored: " + midi_profile_script)
			self.midi_profile_scripts.remove(midi_profile_script)


	def get_midi_env(self, key, default=''):
		if key in self.midi_envs:
			return self.midi_envs[key]
		else:
			return default


	def update_profile(self, script_file_name, request_arguments):
		with open(script_file_name, 'w+') as f:
			f.write('#!/bin/bash\n')
			midiEntries = []
			for parameter in request_arguments:
				if parameter.startswith('ZYNTHIAN_MIDI'):
					value=request_arguments[parameter][0].replace("\n", "\\n")
					value=value.replace("\r", "")
					f.write('export %s="%s"\n' % (parameter, value))
					midiEntries.append(parameter)

			for k in midiEntries:
				del request_arguments[k]
