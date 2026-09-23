/* Copyright 2018 Tronlong Elec. Tech. Co. Ltd. All Rights Reserved. */

#include <stdio.h>
#include <stdbool.h>
#include <libgen.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <sys/select.h>
#include <linux/input.h>

#define INADEQUATE_CONDITIONS 3

typedef enum { KEY_CODE_NONE = 0, KEY_CODE_USER0, KEY_CODE_USER1 } KeyCode;

/* Exit flag */
volatile bool g_quit = false;

/* Short option names */
static const char g_shortopts [] = ":d:vh";

/* Option names */
static const struct option g_longopts [] = {
    { "device",      required_argument,      NULL,        'd' },
    { "version",     no_argument,            NULL,        'v' },
    { "help",        no_argument,            NULL,        'h' },
    { 0, 0, 0, 0 }
};

static void usage(FILE *fp, int argc, char **argv) {
    fprintf(fp,
            "Usage: %s [options]\n\n"
            "Options:\n"
            " -d | --device        Device \n"
            " -v | --version       Display version information\n"
            " -h | --help          Show help content\n\n"
            "", basename(argv[0]));
}

static void opt_parsing_err_handle(int argc, char **argv, int flag) {
    /* Exit if no input parameters are entered  */
    int state = 0;
    if (argc < 2) {
        printf("No input parameters are entered, please check the input.\n");
        state = -1;
    } else {
        /* Feedback Error parameter information then exit */
        if (optind < argc || flag) {
            printf("Error:  Parameter parsing failed\n");
            if (flag)
                printf("\tunrecognized option '%s'\n", argv[optind-1]);

            while (optind < argc) {
                printf("\tunrecognized option '%s'\n", argv[optind++]);
            }

            state = -1;
        }
    }

    if (state == -1) {
        printf("Tips: '-h' or '--help' to get help\n\n");
        exit(2);
    }
}

void sig_handle(int arg) {
    g_quit = true;
}

static int check_button_pressed(int fd) {
    assert(fd >= 0);

    /* wait button being pressed or released. */
    fd_set input;
    FD_ZERO(&input);
    FD_SET(fd, &input);
    int ret = select(fd + 1, &input, NULL, NULL, NULL);
    if (ret < 0) {
        printf("%s", strerror(errno));
        return -1;
    }

    /* read event */
    struct input_event buf;
    if (read(fd, &buf, sizeof(struct input_event)) < 0) {
        printf("%s", strerror(errno));
        return -1;
    }

    /* Check the input_event value */
    switch (buf.code) {
    case KEY_PROG1:
        /* 1: pressed; 0: released */
        if (buf.value == 1)
            return KEY_CODE_USER0;
        break;
    case KEY_PROG2:
        if (buf.value == 1)
            return KEY_CODE_USER1;
        break;
    default:
        return KEY_CODE_NONE;
        break;
    }

    return KEY_CODE_NONE;
}

int main(int argc, char **argv) {
    int c = 0;
    int flag = 0;
    char *dev = NULL;

    /* Parsing input parameters */
    while ((c = getopt_long(argc, argv, g_shortopts, g_longopts, NULL)) != -1) {
        switch (c) {
        case 'd':
            dev = optarg;
            break;

        case 'v':
            /* Display the version */
            printf("version : 1.0\n");
            exit(0);

        case 'h':
            usage(stdout, argc, argv);
            exit(0);
                
        default :
            flag = 1;
            break;
        }
    }

    opt_parsing_err_handle(argc, argv, flag);

    /* Ctrl+c handler */
    signal(SIGINT, sig_handle);

    int fd = open(dev, O_RDONLY);
    if (fd < 0) {
        printf("Error: Failed to open device\n");
        return INADEQUATE_CONDITIONS;
    }
    printf("Please press the key to test.\n");

    while (!g_quit) {
        int key_code = check_button_pressed(fd);
        if (key_code < 0)
            continue;

        switch (key_code) {
            case KEY_CODE_USER0:
            case KEY_CODE_USER1:
                printf("User key pressed!\n");
                break;
            default:
                break;
        }
    }

    close(fd);
    return 0;
}
