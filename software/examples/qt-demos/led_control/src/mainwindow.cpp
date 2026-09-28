/* Copyright 2019 Tronlong Elec. Tech. Co. Ltd. All Rights Reserved. */

#include "mainwindow.h"

#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>

static QString g_led0_path = "/sys/class/leds/user-led1";
static QString g_led1_path = "/sys/class/leds/user-led2";
static QString g_btn_switch_style_sheet = 
            "QPushButton{"
            "   background-color:rgba(0, 0, 0, 100); "
            "   border:8px groove gray; "
            "   border-style:outset; "
            "   border-radius:20px; "
            "   color: white;}"
            "QPushButton:hover{"
            "   background-color:rgba(80, 160, 255, 88); "
            "   color:black;}";
static QString g_btn_exit_style_sheet =
                "QPushButton{"
                "   background-color:rgba(0, 0, 0, 88);"
                "   border-radius:12px; "
                "   color:white;}"
                "QPushButton:hover{"
                "   background-color:rgba(80, 160, 255, 88);"
                "   color:black;}";

MainWindow::MainWindow(QWidget *parent) : QMainWindow(parent) {
    // Show on off status of LEDs.
    m_label[0].setParent(this);
    m_label[1].setParent(this);
    m_label[0].setAlignment(Qt::AlignCenter);
    m_label[1].setAlignment(Qt::AlignCenter);

    // Button to switch LEDs.
    m_btn_switch[0].setParent(this);
    m_btn_switch[1].setParent(this);
    m_btn_switch[0].setText("Switch LED 0");
    m_btn_switch[1].setText("Switch LED 1");
    m_btn_switch[0].setStyleSheet(g_btn_switch_style_sheet);
    m_btn_switch[1].setStyleSheet(g_btn_switch_style_sheet);

    // Button to exit program
    m_btn_exit.setParent(this);
    m_btn_exit.setText("Exit");
    m_btn_exit.setGeometry(20, 20, 80, 25);
    m_btn_exit.setStyleSheet(g_btn_exit_style_sheet);
    m_btn_exit.raise(); // On top of the UI

    connect(&m_btn_exit, SIGNAL(clicked(bool)), this, SLOT(close()));
    connect(&m_btn_switch[0], SIGNAL(clicked(bool)), this, SLOT(handle_btn_clicked(bool)));
    connect(&m_btn_switch[1], SIGNAL(clicked(bool)), this, SLOT(handle_btn_clicked(bool)));

    // Get leds status and update UI
    UpdateLabelStatus(&m_label[0], GetLedStatus(g_led0_path));
    UpdateLabelStatus(&m_label[1], GetLedStatus(g_led1_path));
}

/* Resize labels and buttons according to window's size. */
void MainWindow::resizeEvent(QResizeEvent*) {
    m_label[0].setGeometry(5, 5, this->width() / 2 -10, this->height() / 2 - 10);

    m_label[1].setGeometry(this->width() / 2 + 5, 5,
                           this->width() / 2 - 10, this->height() / 2 - 10);

    m_btn_switch[0].setGeometry(5, this->height() / 2 + 5,
                            this->width() / 2 - 10, this->height() / 2 - 10);

    m_btn_switch[1].setGeometry(this->width() / 2 + 5, this->height() / 2 + 5,
                            this->width() / 2 - 10, this->height() / 2 - 10);
}

// LED status, off: == 0, on: >= 1
int MainWindow::GetLedStatus(const QString &led_path) {
    QString cmd = "cat " + led_path + "/brightness";
    FILE *fp = popen(cmd.toStdString().c_str(), "r");
    if (fp == NULL) {
        return -1;
    }

    char led_status[32];
    if (fgets(led_status, sizeof(led_status), fp) == NULL) {
        printf("fgets error: %s\n", cmd.toStdString().c_str());
        pclose(fp);
        return -1;
    }

    pclose(fp);
    return atoi(led_status);
}

// LED status, off: == 0, on: >= 1
bool MainWindow::SetLedStatus(const QString &led_path, int status) {
    QString cmd = "echo " + QString::number(status) + " > " + led_path + "/brightness";
    if (system(cmd.toStdString().c_str()) == -1) {
        printf("set led status failed!\n");
        return false;
    }
    return true;
}

// LED status, off: == 0, on: >= 1, otherwise label show abnormal state.
void MainWindow::UpdateLabelStatus(QLabel *label, int led_status) {
    QString led_name = "LED 1";
    if (label == &m_label[0]) {
        led_name = "LED 0";
    }

    if (led_status == 0) {
        label->setText(led_name + " is OFF");
        label->setStyleSheet("border-width:1px;"
                           "border-style:solid; "
                           "border-color:white;"
                           "background-color:rgba(88, 88, 88, 200)");
    }
    else if (led_status >= 1) {
        label->setText(led_name + " is ON");
        label->setStyleSheet("border-width:1px;"
                           "border-style:solid; "
                           "border-color:white;"
                           "background-color:rgba(00, 205, 00, 255)");
    }
    else {
        label->setText(led_name + " Abnormal state");
        label->setStyleSheet("border-width:1px;"
                           "border-style:solid;"
                           "border-color:white;"
                           "background-color:rgba(88, 88, 88, 200)");
    }
}

void MainWindow::handle_btn_clicked(bool) {
    QPushButton* btn = qobject_cast<QPushButton*>(sender());

    // Check which button was clicked.
    QLabel *label = &m_label[1];
    QString led_path = g_led1_path;
    if (btn == &m_btn_switch[0]) {
        label = &m_label[0];
        led_path = g_led0_path;
    }

    // Get current LED status and switch it.
    int led_status = GetLedStatus(led_path);
    if (led_status == 0) {
        SetLedStatus(led_path, 1);
    }
    else {
        SetLedStatus(led_path, 0);
    }

    // Get current LED status and update label.
    UpdateLabelStatus(label, GetLedStatus(led_path));

    return;
}

MainWindow::~MainWindow() {
    /* Do Nothing */
}
