/* Copyright 2023 Tronlong Elec. Tech. Co. Ltd. All Rights Reserved. */

#include "mainwindow.h"
#include <QApplication>
#include <QScreen>

int main(int argc, char *argv[]) {
    QApplication a(argc, argv);

    MainWindow w;

    // Get main Screen resolution.
    QScreen *screen = QGuiApplication::primaryScreen();
    QRect screenGeometry = screen->geometry();

    // Set main window size.
    w.resize(screenGeometry.width(), screenGeometry.height());
    w.show();

    // This will not return until main window close.
    return a.exec();
}