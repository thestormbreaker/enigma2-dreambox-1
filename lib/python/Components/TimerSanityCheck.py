import NavigationInstance
from time import localtime, mktime, gmtime, time
from enigma import iServiceInformation, eServiceCenter, eServiceReference, getBestPlayableServiceReference
from timer import TimerEntry
import RecordTimer
from Tools.CIHelper import cihelper
from Components.config import config


class TimerSanityCheck:
	def __init__(self, timerlist, newtimer=None):
		self.localtimediff = 25 * 3600 - mktime(gmtime(25 * 3600))
		self.timerlist = timerlist
		self.newtimer = newtimer
		self.simultimer = []
		self.rep_eventlist = []
		self.nrep_eventlist = []
		self.bflag = -1
		self.eflag = 1

	def check(self, ext_timer=None):
		if ext_timer and isinstance(ext_timer, RecordTimer.RecordTimerEntry):
			self.newtimer = ext_timer
		self.simultimer = []
		if self.newtimer:
			if not self.newtimer.conflict_detection or (self.newtimer.service_ref and '%3a//' in self.newtimer.service_ref.ref.toString()):
				print("[TimerSanityCheck] Exception - timer does not have to be checked!")
				return True
			self.simultimer = [self.newtimer]
		return self.checkTimerlist()

	def getSimulTimerList(self):
		return self.simultimer

	def doubleCheck(self):
		if self.newtimer and self.newtimer.service_ref and self.newtimer.service_ref.ref.valid():
			self.simultimer = [self.newtimer]
			for timer in self.timerlist:
				if timer == self.newtimer:
					return True
				if self.newtimer.begin >= timer.begin and self.newtimer.end <= timer.end:
					if timer.justplay and not self.newtimer.justplay:
						continue
					if timer.service_ref.ref.flags & eServiceReference.isGroup:
						if self.newtimer.service_ref.ref.flags & eServiceReference.isGroup and timer.service_ref.ref.getPath() == self.newtimer.service_ref.ref.getPath():
							return True
						continue
					getUnsignedDataRef1 = timer.service_ref.ref.getUnsignedData
					getUnsignedDataRef2 = self.newtimer.service_ref.ref.getUnsignedData
					for x in (1, 2, 3, 4):
						if getUnsignedDataRef1(x) != getUnsignedDataRef2(x):
							break
					else:
						return True
		return False

	def checkTimerlist(self, ext_timer=None):
		#with special service for external plugins
		# Entries in eventlist
		# timeindex
		# BeginEndFlag 1 for begin, -1 for end
		# index -1 for the new Timer, 0..n index of the existing timers
		# count of running timers

		serviceHandler = eServiceCenter.getInstance()
# create a list with all start and end times
# split it into recurring and singleshot timers

##################################################################################
# process the new timer
		self.rep_eventlist = []
		self.nrep_eventlist = []
		if ext_timer and isinstance(ext_timer, RecordTimer.RecordTimerEntry):
			self.newtimer = ext_timer
		if not self.newtimer or not self.newtimer.service_ref or not self.newtimer.service_ref.ref.valid():
			print("[TimerSanityCheck] Error - timer not valid!")
			return False
		if self.newtimer.disabled or not self.newtimer.conflict_detection or '%3a//' in self.newtimer.service_ref.ref.toString():
			print("[TimerSanityCheck] Exception - timer does not have to be checked!")
			return True
		curtime = localtime(time())
		if curtime.tm_year > 1970 and self.newtimer.end < time():
			print("[TimerSanityCheck] timer is finished!")
			return True
		rflags = self.newtimer.repeated
		rflags = ((rflags & 0x7F) >> 3) | ((rflags & 0x07) << 4)
		if rflags:
			begin = self.newtimer.begin % 86400 # map to first day
			if (self.localtimediff > 0) and ((begin + self.localtimediff) > 86400):
				rflags = ((rflags >> 1) & 0x3F) | ((rflags << 6) & 0x40)
			elif (self.localtimediff < 0) and (begin < self.localtimediff):
				rflags = ((rflags << 1) & 0x7E) | ((rflags >> 6) & 0x01)
			while rflags: # then arrange on the week
				if rflags & 1:
					self.rep_eventlist.append((begin, -1))
				begin += 86400
				rflags >>= 1
		else:
			self.nrep_eventlist.extend([(self.newtimer.begin, self.bflag, -1), (self.newtimer.end, self.eflag, -1)])

##################################################################################
# now process existing timers
		self.check_timerlist = []
		idx = 0
		for timer in self.timerlist:
			if timer != self.newtimer:
				if timer.disabled or not timer.conflict_detection or not timer.service_ref or '%3a//' in timer.service_ref.ref.toString() or timer.state == TimerEntry.StateEnded:
					continue
				if timer.repeated:
					rflags = timer.repeated
					rflags = ((rflags & 0x7F) >> 3) | ((rflags & 0x07) << 4)
					begin = timer.begin % 86400 # map all to first day
					if (self.localtimediff > 0) and ((begin + self.localtimediff) > 86400):
						rflags = ((rflags >> 1) & 0x3F) | ((rflags << 6) & 0x40)
					elif (self.localtimediff < 0) and (begin < self.localtimediff):
						rflags = ((rflags << 1) & 0x7E) | ((rflags >> 6) & 0x01)
					while rflags:
						if rflags & 1:
							self.rep_eventlist.append((begin, idx))
						begin += 86400
						rflags >>= 1
				else:
					self.nrep_eventlist.extend([(timer.begin, self.bflag, idx), (timer.end, self.eflag, idx)])
			self.check_timerlist.append(timer)
			idx += 1

################################################################################
# journalize timer repeations
		if self.nrep_eventlist:
			interval_begin = min(self.nrep_eventlist)[0]
			interval_end = max(self.nrep_eventlist)[0]
			offset_0 = interval_begin - (interval_begin % 604800)
			weeks = (interval_end - offset_0) // 604800
			if (interval_end - offset_0) % 604800:
				weeks += 1
			for cnt in range(int(weeks)):
				for event in self.rep_eventlist:
					if event[1] == -1: # -1 is the identifier of the changed timer
						event_begin = self.newtimer.begin
						event_end = self.newtimer.end
					else:
						event_begin = self.check_timerlist[event[1]].begin
						event_end = self.check_timerlist[event[1]].end
					new_event_begin = event[0] + offset_0 + (cnt * 604800)
					# summertime correction
					new_lth = localtime(new_event_begin).tm_hour
					new_event_begin += 3600 * (localtime(event_begin).tm_hour - new_lth)
					new_event_end = new_event_begin + (event_end - event_begin)
					if event[1] == -1:
						if new_event_begin >= self.newtimer.begin: # is the soap already running?
							self.nrep_eventlist.extend([(new_event_begin, self.bflag, event[1]), (new_event_end, self.eflag, event[1])])
					else:
						if new_event_begin >= self.check_timerlist[event[1]].begin: # is the soap already running?
							self.nrep_eventlist.extend([(new_event_begin, self.bflag, event[1]), (new_event_end, self.eflag, event[1])])
		else:
			offset_0 = 345600 # the Epoch begins on Thursday
			for cnt in (0, 1): # test two weeks to take care of Sunday-Monday transitions
				for event in self.rep_eventlist:
					if event[1] == -1: # -1 is the identifier of the changed timer
						event_begin = self.newtimer.begin
						event_end = self.newtimer.end
					else:
						event_begin = self.check_timerlist[event[1]].begin
						event_end = self.check_timerlist[event[1]].end
					new_event_begin = event[0] + offset_0 + (cnt * 604800)
					new_event_end = new_event_begin + (event_end - event_begin)
					self.nrep_eventlist.extend([(new_event_begin, self.bflag, event[1]), (new_event_end, self.eflag, event[1])])

################################################################################
# order list chronological
		self.nrep_eventlist.sort()

##################################################################################
# detect overlapping timers and overlapping times
		fakeRecList = []
		ConflictTimer = None
		ConflictTunerType = None
		newTimerTunerType = None
		cnt = 0
		idx = 0
		overlaplist = []
		is_ci_timer_conflict = False
		ci_timer = False

		if config.misc.use_ci_assignment.value and not (self.newtimer.record_ecm and not self.newtimer.descramble):
			new_assignment = cihelper.ServiceIsAssigned(self.newtimer.service_ref.ref.toString(), self.newtimer)
			if new_assignment:
				ci_timer = self.newtimer
				ci_timer_dur = ci_timer.end - ci_timer.begin
				ci_timer_events = []
				for ev in self.nrep_eventlist:
					if ev[2] == -1:
						ci_timer_events.append((ev[0], ev[0] + ci_timer_dur))

		for event in self.nrep_eventlist:
			cnt += event[1]
			if event[2] == -1: # new timer
				timer = self.newtimer
			else:
				timer = self.check_timerlist[event[2]]
			if event[1] == self.bflag:
				tunerType = []
				ref = timer.service_ref and timer.service_ref.ref
				timer_ref = timer.service_ref
				if ref and ref.flags & eServiceReference.isGroup and timer.isRunning():
					alternativeref = None
					if not timer.justplay:
						alternativeref = hasattr(timer, "rec_ref") and timer.rec_ref
						if alternativeref:
							timer_ref = alternativeref
					if not alternativeref:
						timer_ref = getBestPlayableServiceReference(timer.service_ref.ref, eServiceReference())
				fakeRecService = NavigationInstance.instance.recordService(timer_ref, True)
				if fakeRecService:
					fakeRecResult = fakeRecService.start(True)
				else:
					fakeRecResult = -1
				# TODO
				#if fakeRecResult == -6 and len(NavigationInstance.instance.getRecordings(True)) < 2:
				#	print("[TimerSanityCheck] less than two timers in the simulated recording list - timer conflict is not plausible - ignored!")
				#	fakeRecResult = 0
				if not fakeRecResult: # tune okay
					if hasattr(fakeRecService, 'frontendInfo'):
						feinfo = fakeRecService.frontendInfo()
						if feinfo and hasattr(feinfo, 'getFrontendData'):
							tunerType.append(feinfo.getFrontendData().get("tuner_type", -1))
						feinfo = None
				else: # tune failed.. so we must go another way to get service type (DVB-S, DVB-T, DVB-C)

					def getServiceType(ref): # helper function to get a service type of a service reference
						serviceInfo = serviceHandler.info(ref)
						serviceInfo = serviceInfo and serviceInfo.getInfoObject(ref, iServiceInformation.sTransponderData)
						return -1 if serviceInfo is None else serviceInfo.get("tuner_type", -1)

					if ref and ref.flags & eServiceReference.isGroup: # service group ?
						serviceList = serviceHandler.list(ref) # get all alternative services
						if serviceList:
							for ref in serviceList.getContent("R"): # iterate over all group service references
								type = getServiceType(ref)
								if not type in tunerType: # just add single time
									tunerType.append(type)
					elif ref:
						tunerType.append(getServiceType(ref))

				if event[2] == -1: # new timer
					newTimerTunerType = tunerType
				overlaplist.append((fakeRecResult, timer, tunerType))
				fakeRecList.append((timer, fakeRecService))
				if fakeRecResult:
					if ConflictTimer is None: # just take care of the first conflict
						ConflictTimer = timer
						ConflictTunerType = tunerType
			elif event[1] == self.eflag:
				for fakeRec in fakeRecList:
					if timer == fakeRec[0] and fakeRec[1]:
						NavigationInstance.instance.stopRecordService(fakeRec[1])
						fakeRecList.remove(fakeRec)
				fakeRec = None
				for entry in overlaplist:
					if entry[1] == timer:
						overlaplist.remove(entry)
			else:
				print("[TimerSanityCheck] bug: unknown flag!")

			if ci_timer and timer != ci_timer and not is_ci_timer_conflict and not (timer.record_ecm and not timer.descramble):
				is_assignment = cihelper.ServiceIsAssigned(timer.service_ref.ref.toString(), timer)
				if is_assignment and new_assignment[0] == is_assignment[0]:
					if event[1] == self.bflag:
						timer_begin = event[0]
						timer_end = event[0] + (timer.end - timer.begin)
					else:
						timer_end = event[0]
						timer_begin = event[0] - (timer.end - timer.begin)
					for ci_ev in ci_timer_events:
						if (ci_ev[0] >= timer_begin and ci_ev[0] <= timer_end) or (ci_ev[1] >= timer_begin and ci_ev[1] <= timer_end):
							timerstr = is_assignment[1] or timer.service_ref.ref.toString()
							ci_timerstr = ci_timer.service_ref.ref.toString()
							if ci_timerstr != timerstr:
								if not ci_timerstr.startswith('1:134:') and not timerstr.startswith('1:134:') and cihelper.canMultiDescramble(is_assignment[0]):
									eService = eServiceReference(timerstr)
									eService1 = ci_timer.service_ref.ref
									for x in (4, 2, 3):
										if eService.getUnsignedData(x) != eService1.getUnsignedData(x):
											is_ci_timer_conflict = True
											break
								else:
									is_ci_timer_conflict = True
								if is_ci_timer_conflict:
									break
					if is_ci_timer_conflict and ConflictTimer is None:
						ConflictTimer = timer
						ConflictTunerType = tunerType

			self.nrep_eventlist[idx] = (event[0], event[1], event[2], cnt, overlaplist[:]) # insert a duplicate into current overlaplist
			fakeRecService = None
			idx += 1

		if ConflictTimer is None:
			print("[TimerSanityCheck] conflict not found!")
			return True

##################################################################################
# we have detected a conflict, now we must figure out the involved timers

		if self.newtimer is not ConflictTimer: # the new timer is not the conflicting timer?
			for event in self.nrep_eventlist:
				if len(event[4]) > 1: # entry in overlaplist of this event??
					kt = False
					nt = False
					for entry in event[4]:
						if entry[1] is ConflictTimer:
							kt = True
						if entry[1] is self.newtimer:
							nt = True
					if nt and kt:
						ConflictTimer = self.newtimer
						ConflictTunerType = newTimerTunerType
						break

		self.simultimer = [ConflictTimer]
		for event in self.nrep_eventlist:
			if len(event[4]) > 1: # entry in overlaplist of this event??
				for entry in event[4]:
					if entry[1] is ConflictTimer:
						break
				else:
					continue
				for entry in event[4]:
					if not entry[1] in self.simultimer:
						for x in entry[2]:
							if x in ConflictTunerType:
								self.simultimer.append(entry[1])
								break

		if len(self.simultimer) < 2:
			print("[TimerSanityCheck] possible bug: unknown conflict!")
			return True

		print("[TimerSanityCheck] conflict detected!")
		return False
