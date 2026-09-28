/* Copyright 2019 Tronlong Elec. Tech. Co. Ltd. All Rights Reserved. */

#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QPushButton>
#include <QLabel>

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    MainWindow(QWidget *parent = 0);
    ~MainWindow();

public slots:
    void handle_btn_clicked(bool);

private:
    QPushButton m_btn_exit;
    QPushButton m_btn_switch[2];
    QLabel      m_label[2];

    int  GetLedStatus(const QString &led_path);
    bool SetLedStatus(const QString &led_path, int status);
    void UpdateLabelStatus(QLabel *label, int led_status);

protected:
    void resizeEvent(QResizeEvent *);
};

#endif // MAINWINDOW_H
