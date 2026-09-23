#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <time.h>
#include <stdbool.h>
#include <errno.h>
#include <inttypes.h>
#include <signal.h>

// Default parameters
#define DEFAULT_CAN_ID 0x123
#define DEFAULT_INTERVAL 0              // Default Send data frame interval 0 us
#define DEFAULT_CAN_FD_LEN 64           // Default CAN FD data len is 64 bytes
#define DEFAULT_Standard_CAN_LEN 8      // Default Standard CAN data len is 8 bytes
#define DEFAULT_TIMEOUT 120             // Default read timeout 120s

#define DEBUG_ERRORS   0                // Simulate bit errors
#define DEBUG_TIME   100                // Simulate times

static bool running = true;

// Write_Data_Info structure
typedef struct {
    uint32_t total_frames_sent;
    ssize_t write_result;
    uint32_t j;
    uint32_t retry;
    struct canfd_frame frame;
    uint32_t debug_times;
} Write_Data_Info;

// Initialize Write_Data_Info structure
void Write_Data_Info_Init(Write_Data_Info *write_Data_info) {
    memset(write_Data_info, 0, sizeof(Write_Data_Info));
}

// Read_Data_Info structure
typedef struct {
    uint32_t error_data;
    uint8_t expected_data;
    ssize_t j;
    struct canfd_frame frame;
    ssize_t read_result;
    uint32_t total_frames_receive;
} Read_Data_Info;

// Initialize Read_Data_Info structure
void Read_Data_Info_Init(Read_Data_Info *read_Data_info) {
    memset(read_Data_info, 0, sizeof(Read_Data_Info));
}

// Update_Read_Data_Info
void Update_Read_Data_Info(Read_Data_Info *read_Data_info) {
    if((read_Data_info->total_frames_receive % 1000 ) == 0){
        printf("Receive %d frames\n",read_Data_info->total_frames_receive);
    }

    // Check data 
    for (int i = 0; i < read_Data_info->frame.len; i++) {
        read_Data_info->expected_data = (i + read_Data_info->j) % 256;
        if (read_Data_info->frame.data[i] != read_Data_info->expected_data) {
            read_Data_info->error_data++;
            printf("Data error detected: expected=0x%02X, got=0x%02X\n", read_Data_info->expected_data, read_Data_info->frame.data[i]);
        }
    }
    read_Data_info->j += read_Data_info->frame.len;
}

// Print_Read_Data_Info
void Print_Read_Data_Info(Read_Data_Info *read_Data_info, double elapsed_time) {
    printf("\n--- Statistics ---\n");
    printf("Total frames received: %u\n", read_Data_info->total_frames_receive);
    printf("Error data : %u\n", read_Data_info->error_data);
    
    double error_rate = (double)read_Data_info->error_data / (read_Data_info->frame.len * read_Data_info->total_frames_receive) * 100;
    printf("Error data rate: %.2f%%\n", error_rate);
    printf("Time elapsed: %.3f seconds\n", elapsed_time);
}

typedef struct {
    char*       can_interface;
    int         interval;
    int         can_mode;          
    bool        write_flag;
    bool        read_flag;
    int         frame_number;
    int         frame_len;
} _Params;

// Initialize _Params structure
void Params_Init(_Params *params) {
    memset(params, 0, sizeof(_Params));
}

// Help Information
void print_help(const char *prog_name) {
    printf("Usage: %s [options]\n", prog_name);
    printf("Options:\n");
    printf("  -d <--device>         CAN interface \n");
    printf("  -r <--read>           Read data as the receiving end\n");
    printf("  -w <--write>          Sending data as a sender\n");
    printf("  -f <--frame>	        Number of data frames sent\n");
    printf("  -l <--length>         The data length of the frame (default values: can 8 bytes, canfd 64 bytes)\n");
    printf("  -i <--interval>       Frame interval duration (unit: us, default is 0)\n");
    printf("  -m <--mode>           Modes (default mode is can mode, 0: can mode, 1: can fd mode)\n");
    printf("  -h <--help>           show this help message\n");
}

// Analyze command-line parameters
bool parse_parameter(_Params *params, int argc, char **argv)
{
    int opt;
    bool flag = false;

    while ((opt = getopt(argc, argv, "d:f:l:i:m:wrh")) != -1) {
        flag = true;
        switch (opt) {
        case 'd':
            params->can_interface = optarg;
            break;
        case 'i':
            params->interval = atoi(optarg);
            break;
        case 'm':
            params->can_mode = atoi(optarg);
            break;
        case 'w':
            params->write_flag = true;
            break;
        case 'f':
            params->frame_number = atoi(optarg);
            break;
        case 'r':
            params->read_flag= true;
            break;
        case 'l':
            params->frame_len = atoi(optarg);
            break;
        case 'h':
            print_help(argv[0]);
            exit(0);
        default:
            flag = false;
            break;
        }
    }
    if (flag == false) {
        printf("Try %s '-h for more information\n", argv[0]);
        exit(-1);
    }

    return true;
}

void sig_handle(int arg) {
    running = false;
}

int init_can(_Params params){
    int s = 0 ;
    if (params.can_mode) {
        s = socket(PF_CAN, SOCK_RAW, CAN_RAW);
        if (s < 0) {
            perror("socket");
            return -1;
        }

        // Enable CAN FD
        int enable = 1;
        if (setsockopt(s, SOL_CAN_RAW, CAN_RAW_FD_FRAMES, &enable, sizeof(enable)) < 0) {
            perror("setsockopt CAN_RAW_FD_FRAMES");
            close(s);
            return -1;
        }
    } else {
        s = socket(PF_CAN, SOCK_RAW, CAN_RAW);
        if (s < 0) {
            perror("socket");
            return -1;
        }
    }

    // Bind to CAN interface
    struct ifreq ifr;
    strcpy(ifr.ifr_name, params.can_interface);
    ioctl(s, SIOCGIFINDEX, &ifr);

    struct sockaddr_can addr;
    memset(&addr, 0, sizeof(addr));
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(s);
        return -1;
    }

    return s;
}

void write_data(int s, _Params *params, Write_Data_Info *write_Data_info){
        // Print configuration information
        printf("CAN Write Configuration:\n");
        printf("  Interface: %s\n", params->can_interface);
        printf("  Write data frame interval: %d us\n", params->interval);
        printf("  CAN ID: 0x%03X\n", DEFAULT_CAN_ID);
        printf("  Mode: %s\n", params->can_mode ? "CAN FD" : "Standard CAN");
        printf("  Frame data len: %d\n", params->frame_len);
        printf("  Send frames number: %d\n", params->frame_number);
        printf("Starting transmission...\n");

        while (running && write_Data_info->total_frames_sent < params->frame_number) {
            memset(&write_Data_info->frame, 0, sizeof(write_Data_info->frame));
            write_Data_info->frame.can_id = DEFAULT_CAN_ID;
            write_Data_info->frame.len = params->frame_len;

            // Fill in data from 0 to 255
            for (size_t i = 0; i <  write_Data_info->frame.len ; i++){
                 write_Data_info->frame.data[i] = (i + write_Data_info->j) % 256;
            }

            // Fill in other data test the error rate
            #if DEBUG_ERRORS
                if(write_Data_info->debug_times < DEBUG_TIME){
                    for (size_t i = 0; i <  write_Data_info->frame.len ; i++){
                         write_Data_info->frame.data[i] = (i+1) % 256;
                    }
                }
            #endif

            // Send Frame
            if (params->can_mode) {
                write_Data_info->write_result = write(s, &write_Data_info->frame, sizeof(struct canfd_frame));
                if(write_Data_info->write_result < 0 && errno == ENOBUFS){
                    write_Data_info->retry ++;
                    usleep(1000); // Error ENOBUFS (No buffer space available) Wait 1000us and retry
                    printf("frame[%d]: Write too quickly, No buffer space available, retry \n",  write_Data_info->total_frames_sent);
                    continue;
                }
                else if (write_Data_info->write_result < 0)
                {
                    perror("write");
                    break;
                }
                 
            } else {
                write_Data_info->write_result = write(s, &write_Data_info->frame, sizeof(struct can_frame));
                if(write_Data_info->write_result < 0 && errno == ENOBUFS){
                    write_Data_info->retry ++;
                    usleep(1000); // Error ENOBUFS (No buffer space available) Wait 1000us and retry
                    printf("frame[%d]: Write too quickly, No buffer space available, retry \n", write_Data_info->total_frames_sent);
                    continue;
                } 
                else if (write_Data_info->write_result < 0)
                {
                    perror("write");
                    break;
                }
            }

            write_Data_info->j += write_Data_info->frame.len;
            write_Data_info->total_frames_sent ++;
			write_Data_info->debug_times ++;
            usleep(params->interval);
        }

        printf("Send completed.\n");
        printf("Total frames sent: %u\n", write_Data_info->total_frames_sent);
        printf("Retry times: %d\n", write_Data_info->retry);
}

void read_data(int s, _Params *params, Read_Data_Info *read_Data_info){
        // Print configuration information
        printf("CAN Read Configuration:\n");
        printf("  Interface: %s\n", params->can_interface);
        printf("  Mode: %s\n", params->can_mode ? "CAN FD" : "Standard CAN");

        struct timeval timeout;
        timeout.tv_sec = DEFAULT_TIMEOUT;
        timeout.tv_usec = 0;

        // Statistics of receiving time
        double total_elapsed_time = 0.0;
        double frame_time = 0.0;
        struct timeval t_frame_start, t_frame_end;

        int ret = 0;

        while (running ) {
            // If receive frame number is enough so break out
            if(params->frame_number > 0 && read_Data_info->total_frames_receive == params->frame_number){
                break;
            }

            // Set timeout
            fd_set readSet;
            FD_ZERO(&readSet);
            FD_SET(s, &readSet);
            
            ret = select(s + 1, &readSet, NULL, NULL, &timeout);
            if (ret < 0) {
                perror("select");
                break;
            } else if (ret == 0) {
                running = false;
                printf("read time out \n");
                break;
            }

            // Receive CAN frames
            memset(&read_Data_info->frame, 0, sizeof(read_Data_info->frame));

            // Start receiving data time
            gettimeofday(&t_frame_start, NULL);
            if (params->can_mode) {
                read_Data_info->read_result = read(s, &read_Data_info->frame, sizeof(struct canfd_frame));
                if(read_Data_info->read_result < 0){
                    perror("read");
                    continue;
                }
            } else {
                read_Data_info->read_result = read(s, &read_Data_info->frame, sizeof(struct can_frame));
                if(read_Data_info->read_result < 0){
                    perror("read");
                    continue;
                }
            }

            read_Data_info->total_frames_receive ++;

            // End of data reception time
            gettimeofday(&t_frame_end, NULL);

            // Calculation the time
            frame_time = (t_frame_end.tv_sec - t_frame_start.tv_sec) + 
                          (t_frame_end.tv_usec - t_frame_start.tv_usec) / 1000000.0;
            total_elapsed_time += frame_time;

            // Update statistics
            Update_Read_Data_Info(read_Data_info);
        }
        
        // Print the received frame information
        Print_Read_Data_Info(read_Data_info, total_elapsed_time);
}

int main(int argc, char **argv) {
    // Set signal processing
    signal(SIGINT, sig_handle);
    signal(SIGTERM, sig_handle);

    // Initialize Write_Data_Info structure
    Write_Data_Info write_Data_info;
    Write_Data_Info_Init(&write_Data_info);

    // Initialize read_Data_info structure
    Read_Data_Info read_Data_info;
    Read_Data_Info_Init(&read_Data_info);

    // Initialize _Params structure
    _Params params;
    Params_Init(&params);

    //Default is CAN mode
    params.can_mode = 0;

    if (parse_parameter(&params, argc, argv) == false) {
        printf("Please try -h to see usage.\n");
        exit(2);
    }

    if(params.frame_len == 0 && params.can_mode == 1 ){
        params.frame_len = DEFAULT_CAN_FD_LEN;
    }
    else if(params.frame_len == 0 && params.can_mode == 0)
    {
        params.frame_len = DEFAULT_Standard_CAN_LEN;
    }
    
    // Init can socket
    int s = 0 ;
    if((s = init_can(params)) < -1){
        printf("Init can socket fail\n");
        return 1;
    }

    if(params.write_flag){
        write_data(s, &params, &write_Data_info);
    }
    else if(params.read_flag)
    {   
        read_data(s, &params, &read_Data_info);
    }
    
    close(s);
    return 0;
}
