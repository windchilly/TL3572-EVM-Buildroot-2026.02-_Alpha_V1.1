/* Copyright 2018 Tronlong Elec. Tech. Co. Ltd. All Rights Reserved. */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <sys/time.h>
#include <fcntl.h>
#include <termios.h>
#include <string.h>
#include <errno.h>
#include <stdbool.h>
#include <libgen.h>
#include <signal.h>
#include <getopt.h>

#define NOPASS_CONDITIONS 3
#define INADEQUATE_CONDITIONS 10

enum Mode { READ, WRITE, LOOPBACK };

/* Exit flag */
volatile bool g_quit = false;

/* Short option names */
static const char g_shortopts [] = ":d:s:rwvhl";

/* Option names */
static const struct option g_longopts [] = {
    { "device",      required_argument,      NULL,        'd' },
    { "read",        no_argument,            NULL,        'r' },
    { "write",       no_argument,            NULL,        'w' },
    { "loopback",    no_argument,            NULL,        'l' },
    { "size",        required_argument,      NULL,        's' },
    { "version",     no_argument,            NULL,        'v' },
    { "help",        no_argument,            NULL,        'h' },
    { 0, 0, 0, 0 }
};

static void usage(FILE *fp, int argc, char **argv) {
    fprintf(fp,
            "Usage: %s [options]\n\n"
            "Options:\n"
            " -d | --device        Device such as '/dev/ttyS0'\n"
            " -r | --read          Read\n"
            " -w | --write         Write\n"
            " -l | --loopback      loopback test\n"
            " -s | --size          Read size\n"
            " -v | --version       Display version information\n"
            " -h | --help          Show help content\n"
            " e.g. %s -d /dev/ttyS1 -r -s 256\n"
            "      %s -d /dev/ttyS1 -w -s 1024\n"
            "      %s -d /dev/ttyS1 -l -s 1024\n\n"
            "", argv[0], argv[0], argv[0], argv[0]);
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

int init_serial(int *fd, const char *dev) {
    struct termios opt;

    /* open serial device */
    if ((*fd = open(dev, O_RDWR)) < 0) {
        perror("open()");
        return -1;
    }

    /* define termois */
    if (tcgetattr(*fd, &opt) < 0) {
        perror("tcgetattr()");
        return -1;
    }

    opt.c_lflag  &= ~(ICANON | ECHO | ECHOE | ISIG);
    opt.c_oflag  &= ~OPOST;

    /* Character length, make sure to screen out this bit before setting the data bit */
    opt.c_cflag &= ~CSIZE;

    /* No hardware flow control */
    opt.c_cflag &= ~CRTSCTS;

    /* 8-bit data length */
    opt.c_cflag |= CS8;

    /* 1-bit stop bit */
    opt.c_cflag &= ~CSTOPB;

    /* No parity bit */
    opt.c_iflag |= IGNPAR;

    /* Output mode */
    opt.c_oflag = 0;
    
    /* No active terminal mode */
    opt.c_lflag = 0;

    /* Input baud rate */
    if (cfsetispeed(&opt, B115200) < 0)
        return -1;

    /* Output baud rate */
    if (cfsetospeed(&opt, B115200) < 0)
        return -1;

    /* Overflow data can be received, but not read */
    if (tcflush(*fd, TCIFLUSH) < 0)
        return -1;

    if (tcsetattr(*fd, TCSANOW, &opt) < 0)
        return -1;

    return 0;
}

int serial_write(int *fd, const char *data, size_t size) {
    int ret = write(*fd, data, size);
    if ( ret < 0 ) {
        perror("write");
        tcflush(*fd, TCOFLUSH);
    }

    return ret;
}

int serial_read(int *fd, char *data, size_t size) {
    size_t read_left = size;
    size_t read_size = 0;
    char *read_ptr = data;
    struct timeval timeout = {5, 0};

    memset(data, 0, size);

    fd_set rfds;
    while (!g_quit) {
        FD_ZERO(&rfds);
        FD_SET(*fd, &rfds);
        timeout.tv_sec = 5;
        timeout.tv_usec = 0;

        if (read_left == 0)
            break;

        switch (select(*fd+1, &rfds, NULL, NULL, &timeout)) {
        case -1:
            perror("select()");
            break;
        case 0:
            perror("timeout and retry");
            break;
        default:
            if (FD_ISSET(*fd,&rfds)) {
                read_size = read(*fd, read_ptr, read_left);
                if (read_size == 0)
                    break;

                read_ptr += read_size;
                read_left -= read_size;
            }
        }
    }

    return read_size;
}

int run_read_mode(char *dev, size_t size) {
    char *buf = NULL;
    int fd = -1;
    int ret = -1;

    ret = init_serial(&fd, dev);
    if (ret < 0) {
        close(fd);
        return -1;
    }

    printf("Mode : read\n");
    if (size <= 0) {
        printf ("Error : Incorrect size settings\n");
        exit(INADEQUATE_CONDITIONS);
    }
    
    buf = (char*)malloc(size + 1);
    buf[size] = '\0';
    ret = serial_read(&fd, buf, size);
    printf("recv: %s\nsize: %d\n", buf, ret);

    free(buf);
    return 0;
}

int run_write_mode(char *dev, size_t size) {
    int fd = -1;
    int ret = -1;

    ret = init_serial(&fd, dev);
    if (ret < 0) {
        close(fd);
        return -1;
    }

    printf("Mode : write\n");
    if (size <= 0) {
        printf("Error : Incorrect size settings\n");
        exit(INADEQUATE_CONDITIONS);
    }

    int i = 0;
    char context;
    size_t write_size = 0;
    while (!g_quit) {
        if (i > 7)
            i = 0;
        context = (char)('0' + i);
            
        write_size += serial_write(&fd, &context, sizeof(context));
        i ++;

        if (size == write_size)
            break;
    }

    printf("send size: %zd\n", write_size);
    return 0;
}

int run_loopback_test(char *dev, size_t size) {
    int fd;
    int ret;
    size_t buf_size;
    int serial_buf_size;

    ret = init_serial(&fd, dev);
    if (ret < 0)
        return -1;

    printf("Start uart loopback testing.\n");

    /* Serial port buffer size generally defaults to 2k - 4k */
    char *write_buf = (char*)malloc(size);
    char *read_buf = (char*)malloc(size);

    buf_size = size;
    while (buf_size > 0)
    {
        if(buf_size > 1024) {
            serial_buf_size = 1024;
        } else {
            serial_buf_size = buf_size;
        }

        // Generate random data to write.
        memset(write_buf, rand() % 26 + 65, serial_buf_size);
        memset(read_buf, 0, serial_buf_size);

        ret = serial_write(&fd, write_buf, serial_buf_size);
        

        /* delay > 1024 / 115200 * 1000000 */
        usleep(90000);

        ret = serial_read(&fd, read_buf, serial_buf_size);
        

        ret = memcmp(read_buf, write_buf, serial_buf_size);
        if (ret != 0) {
            printf("Result : Test failed\n");
            goto release;
        }

        buf_size -= 1024;
    }
    printf("send size: %zd\n", size);
    printf("recv size: %zd\n", size);
    printf("Result : Test pass\n");

release:
    free(write_buf);
    free(read_buf);
    close (fd);
    if (ret != 0) {
        return NOPASS_CONDITIONS;
    } else {
        return 0;
    }
}


int main(int argc, char *argv[]) {
    int c = 0;
    int flag = 0;
    int mode = -1;
    size_t size = 0;
    char *dev = NULL;
    int ret = -1;

    /* Parsing input parameters */
    while ((c = getopt_long(argc, argv, g_shortopts, g_longopts, NULL)) != -1) {
        switch (c) {
        case 'd':
            dev = optarg;
            break;

        case 'r':
            mode = READ;
            break;

        case 'w':
            mode = WRITE;
            break;
            
        case 'l':
            mode = LOOPBACK;
            break;

        case 's':
            size = atoi(optarg);
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

    switch (mode) {
    case READ:
        if(run_read_mode(dev, size) < 0) {
            return INADEQUATE_CONDITIONS;
        }
        break;

    case WRITE:
        if(run_write_mode(dev, size) < 0) {
            return INADEQUATE_CONDITIONS;
        }
        break;

    case LOOPBACK:
        ret = run_loopback_test(dev, size);
        if(ret < 0) {
            return INADEQUATE_CONDITIONS;
        } else if(ret == NOPASS_CONDITIONS) {
            return NOPASS_CONDITIONS;
        }
        break;
    default:
        break;
    }

    return 0;
}
