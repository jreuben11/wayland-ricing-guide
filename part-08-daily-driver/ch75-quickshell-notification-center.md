# Chapter 75 — Quickshell Notification Center: Full Sidebar Implementation

## Contents

- [Overview](#overview)
- [Sections](#sections)
  - [75.1 Architecture](#751-architecture)
  - [75.2 The Notification Store Singleton](#752-the-notification-store-singleton)
  - [75.3 Toast Popup Component](#753-toast-popup-component)
  - [75.4 Toast Card Design](#754-toast-card-design)
  - [75.5 Notification Center Drawer](#755-notification-center-drawer)
  - [75.6 Triggering the Center from the Bar](#756-triggering-the-center-from-the-bar)
  - [75.7 Do-Not-Disturb Mode](#757-do-not-disturb-mode)

---


## Overview
A notification center (persistent sidebar showing notification history) is one
of the most-requested Quickshell components. This chapter builds one end-to-end:
popup toasts + dismissal + persistent history drawer.

## Sections

### 75.1 Architecture

```
NotificationServer (D-Bus listener)
    │
    ├── ActiveNotifications (live popups, timeout-dismissed)
    │       └── PanelWindow (WlrLayer.Overlay, top-right)
    │           └── Repeater of toast cards
    │
    └── NotificationHistory (persisted even after dismiss)
            └── NotificationCenter (WlrLayer.Top, right edge)
                └── Drawer that slides in/out
```

### 75.2 The Notification Store Singleton

```qml
// services/NotificationStore.qml
pragma Singleton
import Quickshell
import Quickshell.Services.Notifications

Singleton {
    property list<var> history: []
    property int unreadCount: 0

    NotificationServer {
        onNotification: notif => {
            // Add to live popups
            popupModel.insert(0, {
                id: notif.id,
                summary: notif.summary,
                body: notif.body,
                appName: notif.appName,
                appIcon: notif.appIcon,
                urgency: notif.urgency,
                timestamp: new Date(),
                notification: notif
            })

            // Also add to persistent history
            NotificationStore.history.unshift({
                summary: notif.summary,
                body: notif.body,
                appName: notif.appName,
                appIcon: notif.appIcon,
                timestamp: new Date()
            })
            NotificationStore.unreadCount++

            // Auto-dismiss non-critical after timeout
            if (notif.urgency !== NotificationUrgency.Critical) {
                dismissTimer.createObject(null, {notifId: notif.id})
            }
        }
    }

    property var popupModel: ListModel {}
}
```

### 75.3 Toast Popup Component

```qml
// notifications/ToastPopup.qml
PanelWindow {
    screen: Quickshell.screens[0]
    layer: WlrLayer.Overlay
    anchors { top: true; right: true }
    margins { top: 48; right: 12 }
    width: 360
    height: toastList.contentHeight + 16
    color: "transparent"
    exclusiveZone: -1  // don't push windows

    ListView {
        id: toastList
        anchors.fill: parent
        model: NotificationStore.popupModel
        spacing: 8

        delegate: ToastCard {
            required property var modelData
            required property int index

            summary: modelData.summary
            body: modelData.body
            appName: modelData.appName
            appIcon: modelData.appIcon
            urgency: modelData.urgency

            onDismissed: NotificationStore.popupModel.remove(index, 1)
            onActionInvoked: id => modelData.notification.invoke(id)
        }

        add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 200 } }
        remove: Transition { NumberAnimation { property: "opacity"; to: 0; duration: 150 } }
    }
}
```

### 75.4 Toast Card Design

```qml
// notifications/ToastCard.qml
import Quickshell.Widgets

Rectangle {
    id: root
    required property string summary
    required property string body
    required property string appName
    required property string appIcon
    required property int urgency
    signal dismissed()
    signal actionInvoked(string id)

    width: 360
    height: layout.implicitHeight + 24
    radius: 12
    color: urgency === 2 ? "#3d1a1a" : "#1e1e2e"
    border.color: urgency === 2 ? "#f38ba8" : "#313244"
    border.width: 1

    // Dismiss timer
    Timer {
        interval: urgency === 2 ? 0 : 5000  // critical = no auto-dismiss
        running: urgency !== 2
        onTriggered: root.dismissed()
    }

    RowLayout {
        id: layout
        anchors { fill: parent; margins: 12 }
        spacing: 12

        IconImage {
            source: root.appIcon
            implicitSize: 32
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text: root.summary
                color: "#cdd6f4"
                font { bold: true; pixelSize: 14 }
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Text {
                text: root.body
                color: "#a6adc8"
                font.pixelSize: 12
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                Layout.fillWidth: true
                visible: root.body.length > 0
            }
        }

        // Dismiss button
        MouseArea {
            width: 20; height: 20
            onClicked: root.dismissed()
            Text { anchors.centerIn: parent; text: "✕"; color: "#6c7086" }
        }
    }

    MouseArea {
        anchors.fill: parent
        propagateComposedEvents: true
        onClicked: root.dismissed()
    }
}
```

### 75.5 Notification Center Drawer

```qml
// notifications/NotificationCenter.qml
PanelWindow {
    id: center
    property bool open: false
    screen: Quickshell.screens[0]
    layer: WlrLayer.Top
    anchors { top: true; right: true; bottom: true }
    width: open ? 380 : 0
    color: "#181825"
    exclusiveZone: open ? width : 0

    Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

    ColumnLayout {
        anchors { fill: parent; margins: 16 }
        spacing: 12
        opacity: center.open ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 150 } }

        // Header
        RowLayout {
            Text { text: "Notifications"; color: "#cdd6f4"; font { bold: true; pixelSize: 16 } }
            Item { Layout.fillWidth: true }
            Text {
                text: NotificationStore.unreadCount + " new"
                color: "#89b4fa"
                font.pixelSize: 12
                visible: NotificationStore.unreadCount > 0
            }
            MouseArea {
                width: 60; height: 24
                onClicked: { NotificationStore.history = []; NotificationStore.unreadCount = 0 }
                Text { anchors.centerIn: parent; text: "Clear all"; color: "#6c7086"; font.pixelSize: 12 }
            }
        }

        // History list
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: NotificationStore.history
            spacing: 8
            clip: true
            delegate: HistoryCard {
                required property var modelData
                width: parent.width
            }
        }

        // Empty state
        Text {
            text: "No notifications"
            color: "#6c7086"
            Layout.alignment: Qt.AlignHCenter
            visible: NotificationStore.history.length === 0
        }
    }
}
```

### 75.6 Triggering the Center from the Bar

```qml
// In Bar.qml
MouseArea {
    onClicked: NotificationCenter.open = !NotificationCenter.open

    RowLayout {
        IconImage { source: "notification-symbolic" }
        Text {
            text: NotificationStore.unreadCount > 0 ? NotificationStore.unreadCount : ""
            color: "#f38ba8"
            visible: NotificationStore.unreadCount > 0
        }
    }
}
```

### 75.7 Do-Not-Disturb Mode

```qml
// In NotificationStore singleton
property bool dnd: false

NotificationServer {
    onNotification: notif => {
        if (NotificationStore.dnd && notif.urgency < NotificationUrgency.Critical) {
            // Store in history but don't show popup
            addToHistory(notif)
            return
        }
        // ... normal popup flow
    }
}
```


---

&copy; [jreuben11](https://github.com/jreuben11). Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).