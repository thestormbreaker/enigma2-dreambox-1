from Components.GUIComponent import GUIComponent
from Components.config import KEY_LEFT, KEY_RIGHT, KEY_HOME, KEY_END, KEY_0, KEY_DELETE, KEY_BACKSPACE, KEY_OK, KEY_TOGGLEOW, KEY_ASCII, KEY_TIMEOUT, KEY_NUMBERS, ConfigElement
from Components.ActionMap import NumberActionMap, ActionMap
from enigma import eListbox, eListboxPythonConfigContent, eRCInput, eTimer
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from skin import applySkinFactor, parameters


class ConfigList(GUIComponent):
	def __init__(self, list, session=None):
		GUIComponent.__init__(self)
		self.l = eListboxPythonConfigContent()
		seperation = parameters.get("ConfigListSeperator", applySkinFactor(200))
		self.l.setSeperation(seperation)
		height, space = parameters.get("ConfigListSlider", applySkinFactor(17, 0))
		self.l.setSlider(height, space)
		self.timer = eTimer()
		self.list = list
		self.onSelectionChanged = []
		self.current = None
		self.session = session

	def execBegin(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmAscii)
		self.timer.callback.append(self.timeout)

	def execEnd(self):
		rcinput = eRCInput.getInstance()
		rcinput.setKeyboardMode(rcinput.kmNone)
		self.timer.callback.remove(self.timeout)

	def toggle(self):
		selection = self.getCurrent()
		selection[1].toggle()
		self.invalidateCurrent()

	def handleKey(self, key):
		selection = self.getCurrent()
		if selection and selection[1].enabled:
			selection[1].handleKey(key)
			self.invalidateCurrent()
			if key in KEY_NUMBERS:
				self.timer.start(1000, 1)

	def getCurrent(self):
		return self.l.getCurrentSelection()

	def getCurrentIndex(self):
		return self.l.getCurrentSelectionIndex()

	def setCurrentIndex(self, index):
		if self.instance is not None:
			self.instance.moveSelectionTo(index)

	def invalidateCurrent(self):
		self.l.invalidateEntry(self.l.getCurrentSelectionIndex())

	def invalidate(self, entry):
		# when the entry to invalidate does not exist, just ignore the request.
		# this eases up conditional setup screens a lot.
		if entry in self.__list:
			self.l.invalidateEntry(self.__list.index(entry))

	GUI_WIDGET = eListbox

	def selectionChanged(self):
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].onDeselect(self.session)
		self.current = self.getCurrent()
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].onSelect(self.session)
		else:
			return
		for x in self.onSelectionChanged:
			x()

	def hideHelp(self):
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].hideHelp(self.session)

	def showHelp(self):
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].showHelp(self.session)

	def postWidgetCreate(self, instance):
		instance.selectionChanged.get().append(self.selectionChanged)
		instance.setContent(self.l)
		self.instance.setWrapAround(True)

	def preWidgetRemove(self, instance):
		if isinstance(self.current, tuple) and len(self.current) >= 2:
			self.current[1].onDeselect(self.session)
		instance.selectionChanged.get().remove(self.selectionChanged)
		instance.setContent(None)

	def setList(self, l):
		self.timer.stop()
		self.__list = l
		self.l.setList(self.__list)

		if l is not None:
			for x in l:
				assert len(x) < 2 or isinstance(x[1], ConfigElement), "entry in ConfigList " + str(x[1]) + " must be a ConfigElement"

	def getList(self):
		return self.__list

	list = property(getList, setList)

	def timeout(self):
		self.handleKey(KEY_TIMEOUT)

	def isChanged(self):
		is_changed = False
		for x in self.list:
			is_changed |= x[1].isChanged()

		return is_changed

	def pageUp(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.pageUp)

	def pageDown(self):
		if self.instance is not None:
			self.instance.moveSelection(self.instance.pageDown)

	def selectionEnabled(self, enabled):
		if self.instance is not None:
			self.instance.setSelectionEnable(enabled)


class ConfigListScreen:
	def __init__(self, list, session=None, on_change=None):
		self["config_actions"] = NumberActionMap(["SetupActions", "InputAsciiActions", "KeyboardInputActions"], {
			"gotAsciiCode": self.keyGotAscii,
			"ok": self.keyOK,
			"left": self.keyLeft,
			"right": self.keyRight,
			"home": self.keyHome,
			"end": self.keyEnd,
			"deleteForward": self.keyDelete,
			"deleteBackward": self.keyBackspace,
			"toggleOverwrite": self.keyToggleOW,
			"pageUp": self.keyPageUp,
			"pageDown": self.keyPageDown,
			"1": self.keyNumberGlobal,
			"2": self.keyNumberGlobal,
			"3": self.keyNumberGlobal,
			"4": self.keyNumberGlobal,
			"5": self.keyNumberGlobal,
			"6": self.keyNumberGlobal,
			"7": self.keyNumberGlobal,
			"8": self.keyNumberGlobal,
			"9": self.keyNumberGlobal,
			"0": self.keyNumberGlobal,
			"file": self.keyFile
		}, -1)  # to prevent left/right overriding the listbox

		self.onChangedEntry = []
		self.onSave = []

		self["VirtualKB"] = ActionMap(["VirtualKeyboardActions"], {
			"showVirtualKeyboard": self.KeyText,
		}, -2)
		self["VirtualKB"].setEnabled(False)

		self["config"] = ConfigList(list, session=session)

		if on_change is not None:
			self.__changed = on_change
		else:
			self.__changed = lambda: None

		if self.handleInputHelpers not in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.handleInputHelpers)

	def createSummary(self):
		from Screens.Setup import SetupSummary
		return SetupSummary

	def getCurrentItem(self):
		return self["config"].getCurrent() and self["config"].getCurrent()[1] or None

	def getCurrentEntry(self):
		return self["config"].getCurrent() and self["config"].getCurrent()[0] or ""

	def getCurrentValue(self):
		return self["config"].getCurrent() and len(self["config"].getCurrent()) > 1 and str(self["config"].getCurrent()[1].getText()) or ""

	def getCurrentDescription(self):
		return self["config"].getCurrent() and len(self["config"].getCurrent()) > 2 and self["config"].getCurrent()[2] or ""

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def handleInputHelpers(self):
		if self["config"].getCurrent() is not None and self["config"].getCurrent()[1].__class__.__name__ in ('ConfigText', 'ConfigPassword'):
			if "VKeyIcon" in self:
				self["VirtualKB"].setEnabled(True)
				self["VKeyIcon"].boolean = True
			if "HelpWindow" in self and self["config"].getCurrent()[1].help_window and self["config"].getCurrent()[1].help_window.instance is not None:
				helpwindowpos = self["HelpWindow"].getPosition()
				from enigma import ePoint
				self["config"].getCurrent()[1].help_window.instance.move(ePoint(helpwindowpos[0], helpwindowpos[1]))
		elif "VKeyIcon" in self:
			self["VirtualKB"].setEnabled(False)
			self["VKeyIcon"].boolean = False
		if "description" in self:
			self["description"].text = self.getCurrentDescription()

	def KeyText(self):
		self["config"].hideHelp()
		from Screens.VirtualKeyBoard import VirtualKeyBoard
		self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title=self["config"].getCurrent()[0], text=self["config"].getCurrent()[1].getValue())

	def VirtualKeyBoardCallback(self, callback=None):
		if callback is not None:
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())
			self.__changed()
		self["config"].showHelp()

	def keyOK(self):
		self["config"].handleKey(KEY_OK)

	def keyLeft(self):
		self["config"].handleKey(KEY_LEFT)
		self.__changed()

	def keyRight(self):
		self["config"].handleKey(KEY_RIGHT)
		self.__changed()

	def keyHome(self):
		self["config"].handleKey(KEY_HOME)
		self.__changed()

	def keyEnd(self):
		self["config"].handleKey(KEY_END)
		self.__changed()

	def keyDelete(self):
		self["config"].handleKey(KEY_DELETE)
		self.__changed()

	def keyBackspace(self):
		self["config"].handleKey(KEY_BACKSPACE)
		self.__changed()

	def keyToggleOW(self):
		self["config"].handleKey(KEY_TOGGLEOW)
		self.__changed()

	def keyGotAscii(self):
		self["config"].handleKey(KEY_ASCII)
		self.__changed()

	def keyNumberGlobal(self, number):
		self["config"].handleKey(KEY_0 + number)
		self.__changed()

	def keyPageDown(self):
		self["config"].pageDown()

	def keyPageUp(self):
		self["config"].pageUp()

	def keyFile(self):
		selection = self["config"].getCurrent()
		if selection and selection[1].enabled and hasattr(selection[1], "description"):
			self.session.openWithCallback(
				self.handleKeyFileCallback, ChoiceBox, selection[0],
				list=list(zip(selection[1].description, selection[1].choices)),
				selection=selection[1].choices.index(selection[1].value),
				keys=[]
			)

	def handleKeyFileCallback(self, answer):
		if answer:
			self["config"].getCurrent()[1].value = answer[1]
			self["config"].invalidateCurrent()
			self.__changed()

	def saveAll(self):
		for x in self["config"].list:
			x[1].save()

	def addSaveNotifier(self, notifier):
		if callable(notifier):
			self.onSave.append(notifier)
		else:
			raise TypeError("[ConfigList] Error: Notifier must be callable!")

	# keySave and keyCancel are just provided in case you need them.
	# you have to call them by yourself.
	def keySave(self):
		self.saveAll()
		self.close()

	def cancelConfirm(self, result):
		if not result:
			self["config"].showHelp()
			return

		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def closeMenuList(self, recursive=False):
		if self["config"].isChanged():
			self["config"].hideHelp()
			self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close(recursive)

	def keyCancel(self):
		self.closeMenuList()

	def closeRecursive(self):
		self.closeMenuList(True)
