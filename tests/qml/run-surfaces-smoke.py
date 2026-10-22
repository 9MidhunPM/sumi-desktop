#!/usr/bin/env python3
"""Render the bar and check layout, tray actions and toast lifecycle offscreen."""
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "config"
import "services" as S
ShellRoot {
    QtObject { id: screenInfo; property int width: 1440; property int height: 900; property string name: "test-output" }
    QtObject {
        id: fakeApp
        property bool barVisible: true
        property string panel: ""
        property var notificationScreen: screenInfo
        function toggle(name, screen) { panel = name; }
        function openSettings(section, screen) { panel = "settings"; }
        function close() { panel = ""; }
    }
    Bar { id: bar; app: fakeApp; modelData: screenInfo }
    NotificationToasts { id: toasts; app: fakeApp }
    TestCase {
        name: "SumiSurfaces"
        when: true
        function assertTrue(condition, message) {
            if (!condition) { console.error("SUMI_SURFACES_FAILED", message); Qt.exit(1); throw new Error(message); }
        }
        function checkStatusControls() {
            const battery = findChild(bar.contentItem, "barBattery");
            const settings = findChild(bar.contentItem, "barSettings");
            const originalWidth = bar.width;
            let stableWidth = 0;
            for (const value of [9, 99, 100]) {
                S.Battery.device = {isPresent: true, percentage: value / 100, state: 0, timeToFull: 0, timeToEmpty: 0};
                for (const width of [759, 760, 999, 1000, 1399, 1400, 1599, 1600, 1920]) {
                    bar.width = width; wait(25);
                    assertTrue(battery.visible === (width >= 760), "Battery visibility at breakpoint " + width);
                    if (!battery.visible) continue;
                    if (!stableWidth) stableWidth = battery.width;
                    assertTrue(Math.abs(battery.width - stableWidth) < 0.5 && battery.width < 84, "Battery fits 100% without changing width or excess padding");
                    assertTrue(battery.contentItem.width >= battery.contentItem.implicitWidth - 0.5, "Battery icon and full percentage fit without elision at " + value + "%");
                    const gap = settings.mapToItem(bar.contentItem, 0, 0).x - battery.mapToItem(bar.contentItem, battery.width, 0).x;
                    assertTrue(gap >= 0 && gap <= 5, "Battery and settings have a compact row gap");
                }
            }
            S.Battery.device = {isPresent: false}; wait(25);
            assertTrue(!battery.visible && settings.visible, "Settings stay reachable without a battery");
            S.Battery.device = {isPresent: true, percentage: 1, state: 0, timeToFull: 0, timeToEmpty: 0};
            bar.width = 1920; wait(30);
            for (const pair of [["barAudio", S.Audio], ["barBluetooth", S.Bluetooth]]) {
                const button = findChild(bar.contentItem, pair[0]);
                const before = pair[1].managerCalls;
                fakeApp.panel = "";
                mouseClick(button, button.width / 2, button.height / 2, Qt.RightButton); wait(25);
                assertTrue(pair[1].managerCalls === before + 1 && fakeApp.panel === "", "Right click opens exactly one manager without the left-click settings route");
                mouseClick(button, button.width / 2, button.height / 2, Qt.LeftButton); wait(25);
                assertTrue(fakeApp.panel === "settings" && pair[1].managerCalls === before + 1, "Left click retains the settings page");
                fakeApp.panel = "";
            }
            bar.width = originalWidth; wait(30);
        }
        function checkMediaGeometry(music, face, period) {
            const spectrum = findChild(music, "musicSpectrum");
            const metadata = findChild(music, "musicMetadata");
            const title = findChild(music, "musicTrackTitle");
            const calendar = findChild(music, "musicCalendarIcon");
            assertTrue(spectrum && metadata && title, "Both media flanks and title exist");
            assertTrue(calendar && (spectrum.opacity <= 0.001 || calendar.opacity <= 0.001), "Calendar returns after the fading spectrum clears its space");
            assertTrue(music.clip && spectrum.clip && metadata.clip && title.clip, "Media viewports prevent spill during the morph");
            const spectrumPoint = spectrum.mapToItem(music, 0, 0);
            const metadataPoint = metadata.mapToItem(music, 0, 0);
            const facePoint = face.mapToItem(music, 0, 0);
            const periodPoint = period.mapToItem(music, 0, 0);
            const titlePoint = title.mapToItem(metadata, 0, 0);
            assertTrue(spectrum.width >= 0 && metadata.width >= 0, "Shrinking media slots never become negative");
            assertTrue(title.text === music.trackText, "Normal, empty and long titles retain their content");
            assertTrue(titlePoint.x >= -0.5 && titlePoint.y >= -0.5 && titlePoint.x + title.width <= metadata.width + 0.5 && titlePoint.y + title.height <= metadata.height + 0.5, "Title stays inside its own clipped viewport");
            for (const item of [spectrum, metadata]) {
                const point = item.mapToItem(music, 0, 0);
                assertTrue(point.y >= -0.5 && point.y + item.height <= music.height + 0.5, "Media content fits the short island height");
            }
            // Zero-width viewports intentionally hide their children while the
            // island collapses. Positive slots must remain clear of the clock.
            if (spectrum.width > 0.5)
                assertTrue(spectrumPoint.x >= 13.5 && spectrumPoint.x + spectrum.width <= facePoint.x - 11.5, "Left spectrum stays between the outer inset and clock digits");
            if (metadata.width > 0.5)
                assertTrue(metadataPoint.x >= periodPoint.x + period.width + 11.5 && metadataPoint.x + metadata.width <= music.width - 13.5, "Right title stays clear of the period and island edge");
            const bars = spectrum.children.filter(item => item.objectName.startsWith("musicSpectrumBar"));
            assertTrue(bars.length === 20, "Visualizer retains twenty actual bars");
            for (let index = 0; index < 20; index++) {
                const item = findChild(spectrum, "musicSpectrumBar" + index);
                assertTrue(item && item.height > 0 && item.height <= spectrum.height + 0.5, "Sample bar " + index + " stays within the visualizer height");
                if (spectrum.width > 0.5) {
                    const point = item.mapToItem(spectrum, 0, 0);
                    assertTrue(point.x >= -0.5 && point.x + item.width <= spectrum.width + 0.5, "Sample bar " + index + " fits its actual responsive viewport");
                    assertTrue(point.y >= -0.5 && Math.abs(point.y + item.height - spectrum.height) <= 0.5, "Sample bar " + index + " stays bottom-aligned");
                }
            }
            if (music.expanded && Math.abs(music.width - music.expandedWidth) <= 0.5) {
                assertTrue(spectrum.width > 0 && metadata.width > 0, "Settled expanded island has usable media slots");
                assertTrue(Math.abs(spectrumPoint.x - 14) <= 0.5 && Math.abs(metadataPoint.x + metadata.width - (music.width - 14)) <= 0.5, "Expanded media uses both sides with fourteen-pixel outer insets");
                const first = findChild(spectrum, "musicSpectrumBar0");
                const last = findChild(spectrum, "musicSpectrumBar19");
                assertTrue(Math.abs(first.x) <= 0.5 && Math.abs(last.x + last.width - spectrum.width) <= 0.5, "First and last bars fill the visualizer's own width");
                assertTrue(bars.some(item => item.height >= spectrum.height - 0.5) && bars.some(item => item.height < spectrum.height / 2), "Nonzero sample fixture exercises tall and short visible bars");
            }
        }
        function checkClock(width, expectedTime) {
            const music = bar.smokeMusicIsland;
            const face = findChild(music, "barClockFace");
            const time = findChild(music, "barClockTime");
            const period = findChild(music, "barClockPeriod");
            assertTrue(face && time && period, "Clock face, time and period exist");
            const center = music.mapToItem(bar.contentItem, 0, 0);
            const digits = time.mapToItem(bar.contentItem, 0, 0);
            const suffix = period.mapToItem(bar.contentItem, 0, 0);
            assertTrue(music.visible && face.visible && time.visible && period.visible, "Clock remains visible at " + width);
            assertTrue(time.font.pixelSize >= 22, "Short bar keeps clock text legible at " + width);
            assertTrue(time.text === (expectedTime || "12:59") && period.text === "PM", "12-hour time and uppercase period at " + width);
            assertTrue(Math.abs(digits.x + time.width / 2 - bar.width / 2) <= 0.5, "Clock digits remain exactly screen-centered at " + width + ": " + time.text);
            assertTrue(digits.x >= center.x && digits.x + time.width <= center.x + music.width && suffix.x >= center.x && suffix.x + period.width <= center.x + music.width, "Digits and period fit their island at " + width);
            assertTrue(digits.y >= center.y && digits.y + time.height <= center.y + music.height && suffix.y >= center.y && suffix.y + period.height <= center.y + music.height, "Clock content fits the short island height at " + width);
            assertTrue(center.x >= bar.smokeLeftEdge && center.x + music.width <= bar.smokeRightEdge, "Both side groups clear the center at " + width);
            assertTrue(music.width <= bar.centerRoom, "Center respects its reserved room at " + width + ": island=" + music.width + " room=" + bar.centerRoom + " sides=" + bar.smokeLeftIsland.width + "/" + bar.smokeRightIsland.width);
            assertTrue(bar.smokeLeftEdge <= bar.smokeRightEdge, "Side groups fit at " + width);
            assertTrue(music.playing === S.Media.playing, "Layout does not falsify playback at " + width);
            assertTrue(!music.expanded || music.playing, "Expanded media requires playback at " + width);
            const demand = fakeApp.barVisible && music.visible && music.expanded;
            assertTrue(bar.visualizationWanted === demand && S.Spectrum.hasVisibleConsumer === demand, "FFT demand follows visible expanded media at " + width);
            assertTrue(Theme.barBackground.a > 0 && Theme.barBackground.a < 1, "Island background is translucent");
            assertTrue(bar.height === 34, "Bar region stays34px tall");
            for (const island of [bar.smokeLeftIsland, music, bar.smokeRightIsland])
                assertTrue(island.visible && island.height === 32, "Three32px islands remain visible at " + width);
            const pixels = grabImage(bar.contentItem);
            const leftGap = Math.floor((bar.smokeLeftEdge + center.x) / 2);
            const rightGap = Math.ceil((center.x + music.width + bar.smokeRightEdge) / 2);
            assertTrue(pixels.alpha(leftGap, Math.floor(bar.height / 2)) === 0 && pixels.alpha(rightGap, Math.floor(bar.height / 2)) === 0, "Both inter-island gaps stay fully transparent at " + width + " time=" + time.text + " island=" + music.width + " panel=" + fakeApp.panel + " alpha=" + [pixels.alpha(leftGap, Math.floor(bar.height / 2)), pixels.alpha(rightGap, Math.floor(bar.height / 2))]);
            for (let id = 1; id <= 5; id++) {
                const workspace = findChild(bar.contentItem, "workspaceButton" + id);
                assertTrue(workspace && workspace.visible, "Base workspace " + id + " remains visible at " + width);
                checkWorkspaceNumber(workspace, id);
            }
            checkMediaGeometry(music, face, period);
        }
        function checkAnimatedClock() {
            const music = bar.smokeMusicIsland;
            Settings.fullMotion = true;
            Settings.reducedMotion = false;
            for (const time of ["1:01", "12:59"]) {
                music.timeText = time;
                S.Media.playing = false; wait(400);
                checkClock(1920, time);
                const collapsedWidth = music.width;
                const expansionWidths = [];
                S.Media.playing = true;
                for (let frame = 0; frame < 24; frame++) {
                    wait(16);
                    checkClock(1920, time);
                    expansionWidths.push(music.width);
                }
                const expandedWidth = music.width;
                assertTrue(expandedWidth > collapsedWidth + 1, "Playing media expands at " + time);
                assertTrue(expansionWidths.some(value => value > collapsedWidth + 0.5 && value < expandedWidth - 0.5), "Expansion checks include actual intermediate widths at " + time);
                const collapseWidths = [];
                S.Media.playing = false;
                for (let frame = 0; frame < 24; frame++) {
                    wait(16);
                    checkClock(1920, time);
                    collapseWidths.push(music.width);
                }
                assertTrue(Math.abs(music.width - collapsedWidth) < 0.5, "Paused media returns to its collapsed width at " + time);
                assertTrue(collapseWidths.some(value => value > collapsedWidth + 0.5 && value < expandedWidth - 0.5), "Collapse checks include actual intermediate widths at " + time);
            }
            Settings.reducedMotion = true;
            music.timeText = "12:59";
            S.Media.playing = true; wait(40);
        }
        function checkAnimatedBar() {
            const content = findChild(bar.contentItem, "barContent");
            assertTrue(content !== null, "Animated bar content exists");
            Settings.reducedMotion = false;
            const closing = [];
            fakeApp.barVisible = false;
            for (let frame = 0; frame < 12; frame++) { wait(16); closing.push(bar.reveal); }
            tryCompare(bar, "reveal", 0, 500);
            assertTrue(closing.some(value => value > 0 && value < 1), "Bar exit has actual intermediate frames");
            assertTrue(!bar.visible && Math.abs(content.mapToItem(bar.contentItem, 0, 0).y + Theme.barHeight + 6) <= 0.5, "Hidden bar slides fully above the screen");
            const opening = [];
            fakeApp.barVisible = true;
            for (let frame = 0; frame < 12; frame++) { wait(16); opening.push(bar.reveal); }
            tryCompare(bar, "reveal", 1, 500);
            assertTrue(opening.some(value => value > 0 && value < 1), "Bar entrance has actual intermediate frames");
            assertTrue(bar.visible && Math.abs(content.mapToItem(bar.contentItem, 0, 0).y) <= 0.5, "Shown bar settles at its original position");
            Settings.reducedMotion = true;
        }
        function checkOriginalSvg(item, label) {
            assertTrue(item !== null, label + " exists");
            tryCompare(item, "status", Image.Ready);
            // QtTest's child-item crop is offset incorrectly in this backend.
            // Sample its mapped position in the containing window instead.
            const pixels = grabImage(bar.contentItem);
            const origin = item.mapToItem(bar.contentItem, 0, 0);
            const redX = Math.floor(origin.x + item.width * 0.2);
            const blueX = Math.floor(origin.x + item.width * 0.75);
            const y = Math.floor(origin.y + item.height / 2);
            assertTrue(pixels.red(redX, y) > 240 && pixels.blue(redX, y) < 15, label + " retains red pixels");
            assertTrue(pixels.blue(blueX, y) > 240 && pixels.red(blueX, y) < 15, label + " retains blue pixels");
        }
        function checkWorkspaceNumber(button, id) {
            const number = findChild(button, "workspaceNumber" + id);
            assertTrue(number && number.visible && number.text === String(id), "Workspace " + id + " keeps its number");
            const local = number.mapToItem(button, 0, 0);
            const inBar = number.mapToItem(bar.contentItem, 0, 0);
            assertTrue(Math.abs(local.x + number.width / 2 - button.width / 2) <= 0.5, "Workspace " + id + " number is horizontally centered in its button");
            assertTrue(Math.abs(local.y + number.height / 2 - button.height / 2) <= 0.5, "Workspace " + id + " number is vertically centered in its button");
            assertTrue(Math.abs(inBar.y + number.height / 2 - bar.height / 2) <= 0.5, "Workspace " + id + " number is vertically centered in the bar");
            return number;
        }
        function checkWindowDots(id, count, urgent) {
            const button = findChild(bar.contentItem, "workspaceButton" + id);
            assertTrue(button !== null, "Workspace " + id + " exists");
            const row = findChild(button, "workspaceOccupancy" + id);
            const number = checkWorkspaceNumber(button, id);
            assertTrue(button && row, "Workspace " + id + " has its occupancy row");
            assertTrue(number && number.visible && number.text === String(id), "Workspace number remains visible above its dots");
            const numberPosition = number.mapToItem(button, 0, 0);
            assertTrue(button.windowCount === count, "Workspace " + id + " reports every actual window");
            assertTrue(row.visible === (count > 0), "Only occupied workspaces show dots: " + id);
            const rowPosition = row.mapToItem(button, 0, 0);
            assertTrue(Math.abs(rowPosition.x + row.width / 2 - button.width / 2) <= 0.5, "Dot row stays centered under workspace " + id);
            const prefix = "workspaceWindowDot" + id + "-";
            const dots = row.children.filter(item => item.objectName.startsWith(prefix));
            assertTrue(dots.length === count, "Workspace " + id + " renders exactly " + count + " dots, received " + dots.length);
            for (let index = 0; index < count; index++) {
                const dot = findChild(row, prefix + index);
                assertTrue(dot && dot.visible && dot.width > 0 && dot.height > 0, "Window dot " + id + "-" + index + " is visible");
                assertTrue(String(dot.color) === String(urgent ? Theme.accentWarn : Theme.accentBlue), "Window dots follow urgency and theme colors");
                const point = dot.mapToItem(button, 0, 0);
                assertTrue(point.x >= 0 && point.y >= 0 && point.x + dot.width <= button.width && point.y + dot.height <= button.height, "Dots fit workspace " + id + ": " + point.x + "," + point.y + " in " + button.width + "x" + button.height);
                assertTrue(point.y >= numberPosition.y + number.height, "Every window dot sits below the number");
            }
        }
        function noWorkspaceAppIcons(item) {
            assertTrue(!item.objectName.startsWith("workspaceAppIcon"), "Workspaces show numbers and window dots without app icons");
            for (const child of item.children) noWorkspaceAppIcons(child);
        }
        function checkTrayActions() {
            let activations = 0;
            let menus = 0;
            const item = {
                hasMenu: true, onlyMenu: false,
                activate: function() { activations++; },
                display: function(parent, x, y) {
                    menus++;
                    assertTrue(parent === bar && x >= 0 && x < bar.width && y === bar.height + 8, "Tray menu receives bar-local placement");
                }
            };
            bar.activateTray(item, false);
            assertTrue(activations === 1 && menus === 0, "Standard tray primary click activates");
            bar.activateTray(item, true);
            assertTrue(activations === 1 && menus === 1, "Standard tray right click opens menu");
            item.onlyMenu = true;
            bar.activateTray(item, false);
            bar.activateTray(item, true);
            assertTrue(activations === 1 && menus === 3, "Menu-only tray supports primary and right click");
            item.onlyMenu = false;
            item.hasMenu = false;
            bar.activateTray(item, true);
            assertTrue(activations === 1 && menus === 3, "Right click without menu does not activate");
            bar.activateTray(item, false);
            assertTrue(activations === 2 && menus === 3, "Menu-less primary click still activates");
        }
        function test_surfaces() {
            Settings.reducedMotion = true;
            S.Media.playing = true;
            wait(200);
            bar.smokeMusicIsland.timeText = "12:59";
            bar.smokeMusicIsland.periodText = "PM";
            bar.smokeMusicIsland.trackText = "A long playing title that must fit around the centered clock";
            bar.smokeMusicIsland.samples = [100, 25, 75, 0, 50, 150, -20, 40, 90, 10, 60, 30, 80, 20, 70, 100, 5, 55, 45, 95];
            assertTrue(bar.workspaceEntries.length === 5, "Exactly five base workspace entries exist");
            bar.monitor = {activeWorkspace: {id: 2}};
            assertTrue(bar.activeWorkspaceId === 2, "Workspace highlight follows this monitor");
            const baseButton = findChild(bar.contentItem, "workspaceButton2");
            const occupancy = findChild(bar.contentItem, "workspaceOccupancy2");
            assertTrue(occupancy !== null, "Workspace occupancy delegate exists");
            for (let update = 0; update < 24; update++) {
                bar.workspaces = [null, {id: 2, toplevels: {values: [{}]}, urgent: true}]; wait(5);
                checkWindowDots(2, 1, true);
                bar.workspaces = [null, {id: 2, toplevels: null}]; wait(5);
                checkWindowDots(2, 0, false);
                bar.workspaces = []; wait(5);
                assertTrue(findChild(bar.contentItem, "workspaceOccupancy2") === occupancy && findChild(bar.contentItem, "workspaceButton2") === baseButton, "Workspace churn preserves base delegate identities");
            }
            const sameClassWindows = Array.from({length: 3}, (_, index) => ({wayland: {appId: "FixtureEditor"}, lastIpcObject: {address: "0x" + (100 + index)}}));
            const otherWindow = {wayland: {appId: "FixtureOther"}};
            for (const windows of [[], [null]]) {
                bar.workspaces = [{id: 8, toplevels: {values: windows}}]; wait(20);
                assertTrue(bar.additionalWorkspaces.length === 0 && findChild(bar.contentItem, "workspaceButton8") === null, "Higher workspace requires a real window");
            }
            bar.workspaces = [{id: 8, toplevels: {values: [sameClassWindows[0]]}}]; wait(30);
            assertTrue(bar.additionalWorkspaces.length === 1 && findChild(bar.contentItem, "workspaceButton8") !== null, "Occupied workspace8 appears dynamically");
            checkWindowDots(8, 1, false);
            bar.workspaces = [{id: 8, toplevels: null}]; wait(30);
            assertTrue(bar.additionalWorkspaces.length === 0 && findChild(bar.contentItem, "workspaceButton8") === null, "Emptied workspace8 disappears");
            for (let id = 6; id <= 10; id++) assertTrue(findChild(bar.contentItem, "workspaceButton" + id) === null, "Empty higher workspace " + id + " is absent");
            bar.workspaces = [];
            checkTrayActions();
            const svgSource = Qt.resolvedUrl("tray-color.svg").toString();
            const providerSource = "image://icon/tray-color.svg?path=" + Qt.resolvedUrl(".").toString().replace("file://", "");
            const entries = [];
            for (let index = 0; index < 12; index++) entries.push({title: "Tray " + index, tooltipTitle: "Tray " + index, icon: index === 1 ? providerSource : svgSource, hasMenu: false, onlyMenu: false});
            bar.trayItems = entries;
            let middleWidthExpands = false;
            for (const width of [600, 960, 1280, 1920]) {
                bar.width = width - 32; wait(100);
                for (const title of ["Midnight Drive", "", "A long playing title that must fit around the centered clock"]) {
                    bar.smokeMusicIsland.trackText = title;
                    checkClock(width);
                }
                if ((width === 960 || width === 1280) && bar.smokeMusicIsland.expanded) middleWidthExpands = true;
                assertTrue(bar.smokeMusicIsland.expanded === (bar.centerRoom >= bar.smokeMusicIsland.expandedWidth), "Playing island expands whenever its reserved room fits at " + width);
                if (width === 600) assertTrue(bar.smokeMusicIsland.playing && !bar.smokeMusicIsland.expanded, "Narrow clock retains true playback without media expansion");
                if (width === 1920) assertTrue(bar.smokeMusicIsland.expanded, "Wide playing bar expands media");
                assertTrue(bar.inlineTrayCount <= 3 && bar.smokeOverflowVisible && bar.smokeTrayMenuCount === 12 - bar.inlineTrayCount, "Tray overflow retains excess applications");
                for (let index = 0; index < bar.smokeTrayMenuCount; index++) {
                    const menuItem = bar.smokeTrayMenu.itemAt(index);
                    assertTrue(menuItem.icon.source.toString() === entries[index + bar.inlineTrayCount].icon, "Overflow preserves complete image URL at " + width);
                    assertTrue(menuItem.icon.color.a === 0, "Overflow preserves original tray colors at " + width);
                }
                for (let index = 0; index < bar.inlineTrayCount; index++) {
                    const trayImage = findChild(bar.smokeTrayRepeater.itemAt(index), "smokeTrayImage");
                    assertTrue(trayImage.source.toString() === entries[index].icon, "Inline tray preserves complete image URL at " + width);
                    if (index === 0) checkOriginalSvg(trayImage, "Inline tray SVG");
                }
            }
            assertTrue(middleWidthExpands, "Compact expanded media fits at a middle desktop width");
            const occupiedWorkspaces = [
                {id: 2, name: "2", toplevels: {values: sameClassWindows}},
                {id: 8, name: "8", toplevels: {values: [otherWindow]}},
                {id: -98, name: "special:magic", toplevels: {values: [sameClassWindows[0]]}}
            ];
            bar.workspaces = occupiedWorkspaces; wait(50);
            assertTrue(bar.workspaceEntries[1].windowCount === 3, "Three windows of the same application remain three windows");
            checkWindowDots(2, 3, false);
            for (const width of [600, 960, 1280, 1920]) {
                bar.width = width - 32; wait(100);
                checkClock(width);
                assertTrue(bar.additionalWorkspaces.length === 1 && bar.additionalWorkspaces[0].id === 8, "Only occupied higher workspace remains in model");
                assertTrue(bar.inlineExtraWorkspaces.some(entry => entry.id === 8) || bar.workspaceMenuEntries.some(entry => entry.id === 8), "Occupied workspace8 remains reachable at " + width);
                for (const id of [6, 7, 9, 10]) assertTrue(findChild(bar.contentItem, "workspaceButton" + id) === null, "Empty workspace " + id + " stays absent with occupied8");
                checkWindowDots(2, 3, false);
                for (const id of [1, 3, 4, 5]) checkWindowDots(id, 0, false);
                if (bar.inlineExtraWorkspaces.some(entry => entry.id === 8)) checkWindowDots(8, 1, false);
                noWorkspaceAppIcons(bar.smokeLeftIsland);
                if ([600, 1280, 1920].indexOf(width) >= 0) grabImage(bar.contentItem).save("/tmp/sumi-bar-" + width + ".png");
            }
            checkStatusControls();
            const workspaceOverflow = findChild(bar.contentItem, "workspaceOverflow");
            assertTrue(workspaceOverflow.text === "" && workspaceOverflow.iconName === "more-horizontal", "Workspace overflow never shows a +count badge");
            const originalTheme = Theme.document;
            Theme.document = Object.assign({}, originalTheme, {colors: Object.assign({}, originalTheme.colors || {}, {accentBlue: "#36b7a5"})});
            wait(80);
            checkWindowDots(2, 3, false);
            checkWindowDots(8, 1, false);
            checkOriginalSvg(findChild(bar.smokeTrayRepeater.itemAt(0), "smokeTrayImage"), "Tray SVG after theme change");
            Theme.document = originalTheme; wait(80);
            checkWindowDots(2, 3, false);
            for (const count of [7, 2, 0, 3]) {
                bar.workspaces = [{id: 2, toplevels: {values: Array.from({length: count}, (_, index) => ({wayland: {appId: "FixtureEditor"}, lastIpcObject: {address: "0x" + (200 + index)}}))}}]; wait(30);
                checkWindowDots(2, count, false);
                assertTrue(findChild(bar.contentItem, "workspaceButton2") === baseButton && findChild(bar.contentItem, "workspaceOccupancy2") === occupancy, "Count changes preserve the base workspace and occupancy row");
                noWorkspaceAppIcons(baseButton);
            }
            bar.workspaces = []; wait(40);
            S.Media.playing = false; wait(80);
            checkClock(1920);
            assertTrue(!bar.smokeMusicIsland.expanded && !S.Spectrum.hasVisibleConsumer, "Paused media collapses and releases FFT demand");
            S.Media.playing = true; wait(80);
            assertTrue(bar.smokeMusicIsland.playing && bar.smokeMusicIsland.expanded && S.Spectrum.hasVisibleConsumer, "Resumed wide media expands and restores FFT demand");
            checkAnimatedClock();
            checkAnimatedBar();
            const music = bar.smokeMusicIsland;
            const clockFace = findChild(music, "barClockFace");
            mouseClick(music, clockFace.x + clockFace.width / 2, music.height / 2);
            assertTrue(fakeApp.panel === "calendar", "Centered clock click opens calendar");
            fakeApp.panel = "";
            const clockPeriod = findChild(music, "barClockPeriod");
            mouseClick(music, clockPeriod.x + clockPeriod.width / 2, music.height / 2);
            assertTrue(fakeApp.panel === "calendar", "AM/PM suffix click opens calendar");
            for (const name of ["musicSpectrum", "musicMetadata"]) {
                fakeApp.panel = "";
                const flank = findChild(music, name);
                const point = flank.mapToItem(music, 0, 0);
                mouseClick(music, point.x + flank.width / 2, music.height / 2);
                assertTrue(fakeApp.panel === "media", name + " click opens media controls");
            }
            fakeApp.panel = "";
            const musicOrigin = music.mapToItem(bar.contentItem, 0, 0);
            mouseMove(bar.contentItem, (bar.smokeLeftEdge + musicOrigin.x) / 2, bar.height / 2);
            fakeApp.barVisible = false; wait(30);
            assertTrue(!bar.visible, "Reduced-motion bar hides immediately");
            assertTrue(!S.Spectrum.hasVisibleConsumer, "Hidden bar releases FFT demand");
            fakeApp.barVisible = true; wait(30);
            assertTrue(bar.visible, "Bar reopens");
            const note = {id: 1, appName: "Test", summary: "First", body: "Toast lifecycle", actions: [], popup: true};
            S.Notifications.history = [note]; wait(100);
            assertTrue(toasts.visible && toasts.smokeCount === 1, "Notification appears");
            S.Notifications.history = [Object.assign({}, note, {summary: "Updated"})]; wait(80);
            assertTrue(toasts.smokeCount === 1 && toasts.smokeFirst.summary === "Updated", "Replace-id updates existing toast");
            S.Desktop.lastError = "The test action failed"; wait(80);
            assertTrue(toasts.smokeCount === 2 && toasts.smokeFirst.error, "Action errors are visible and prioritized");
            S.Desktop.lastError = ""; wait(80);
            assertTrue(toasts.smokeCount === 1, "Action error can be dismissed");
            fakeApp.panel = "settings"; wait(30);
            assertTrue(!toasts.visible, "Toasts yield to open panels");
            fakeApp.panel = ""; wait(30);
            assertTrue(toasts.visible, "Pending toast returns after panel closes");
            Settings.reducedMotion = false;
            S.Notifications.history = []; wait(400);
            assertTrue(!toasts.visible && toasts.smokeCount === 0, "Final removal completes exit animation");
            console.info("SUMI_SURFACES_OK"); Qt.quit();
        }
    }
}
'''


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="sumi-surfaces-") as temporary:
        work = Path(temporary)
        config = work / "shell"
        shutil.copytree(repo / "shell", config)
        media = config / "services/Media.qml"
        media.write_text(media.read_text().replace("readonly property bool playing: player ? player.isPlaying : false", "property bool playing: false"))
        battery = config / "services/Battery.qml"
        battery.write_text(battery.read_text().replace("readonly property var device: Up.UPower.displayDevice", "property var device: ({isPresent: true, percentage: 1, state: 0, timeToFull: 0, timeToEmpty: 0})"))
        for name, command in (("Audio", "audio-manager"), ("Bluetooth", "bluetooth-manager")):
            service = config / "services" / (name + ".qml")
            service.write_text(service.read_text().replace('function openManager(): void { Desktop.action("' + command + '", []); }', 'property int managerCalls: 0\n    function openManager(): void { managerCalls++; }'))
        (config / "tray-color.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><path fill="#ff0000" d="M0 0h10v20H0z"/><path fill="#0000ff" d="M10 0h10v20H10z"/></svg>')
        data = work / "data"
        data.mkdir()
        for filename in ("Bar.qml", "NotificationToasts.qml"):
            path = config / filename
            source = path.read_text().replace("PanelWindow {", "Window {", 1)
            source = re.sub(r"^    (screen:|anchors \{|margins \{|exclusiveZone:|WlrLayershell\.).*\n", "", source, flags=re.M)
            source = re.sub(r"^    implicit(Width|Height):", lambda match: "    " + match[1].lower() + ":", source, flags=re.M)
            if filename == "Bar.qml":
                source = re.sub(r"    readonly property var monitor:.*\n", "    property var monitor: null\n", source)
                source = source.replace("    readonly property var trayItems: SystemTray.items.values", "    property var trayItems: []")
                source = source.replace("readonly property var workspaces: Hyprland.workspaces.values", "property var workspaces: []")
                source = source.replace("model: bar.trayItems.slice(0, bar.inlineTrayCount)", "id: testTrayRepeater\n                    model: bar.trayItems.slice(0, bar.inlineTrayCount)")
                source = source.replace("Image { id: trayImage;", 'Image { id: trayImage; objectName: "smokeTrayImage";')
                source = source.replace('    color: "transparent"', '''    width: 1440
    readonly property real smokeLeftEdge: leftIsland.x + leftIsland.width
    readonly property real smokeRightEdge: rightIsland.x
    readonly property var smokeLeftIsland: leftIsland
    readonly property var smokeRightIsland: rightIsland
    readonly property var smokeMusicIsland: musicIsland
    readonly property var smokeTrayRepeater: testTrayRepeater
    readonly property var smokeTrayMenu: trayMenu
    readonly property bool smokeOverflowVisible: trayOverflow.visible
    readonly property int smokeTrayMenuCount: trayMenu.count
    color: "transparent"''', 1)
            else:
                source = source.replace('    color: "transparent"', '''    readonly property int smokeCount: toastModel.count
    readonly property var smokeFirst: toastModel.count ? toastModel.get(0).entry : ({})
    color: "transparent"''', 1)
            path.write_text(source)
        (config / "shell.qml").write_text(HARNESS)
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, SUMI_PREVIEW="1", SUMI_STATE_DIR=str(work / "state"), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=str(runtime), XDG_DATA_HOME=str(data))
        result = subprocess.run(["qs", "-p", str(config)], env=environment, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or "SUMI_SURFACES_OK" not in output or any(message in output for message in ("TypeError:", "ReferenceError:", "Failed to load configuration", "Unable to assign [undefined]", "FAIL!", "Binding loop")):
            raise SystemExit(output)
        for width in (600, 1280, 1920):
            image = Path(f"/tmp/sumi-bar-{width}.png")
            header = image.read_bytes()[:24]
            if header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != (width - 32, 34):
                raise SystemExit(f"Invalid offscreen bar render: {image}")
        print("Offscreen renders: /tmp/sumi-bar-600.png /tmp/sumi-bar-1280.png /tmp/sumi-bar-1920.png")
        print("Native layer placement and popup menu grabs require compositor validation")


if __name__ == "__main__":
    main()
