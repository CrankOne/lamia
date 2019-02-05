/* Testing app for the `shadow' supervisor script.
 * */
# include <stdio.h>
# include <stdlib.h>
# include <math.h>
# include <unistd.h>
# include <string.h>
# include <time.h>
# include <signal.h>

# ifdef DEBUG
# define dbg_print( ... ) printf( __VA_ARGS__ );
# else
# define dbg_print( ... ) /* nothing */
# endif

typedef int (*StrategyCllb)();

static struct {
    volatile sig_atomic_t _gSigCaught;
    /* Message event appearance rate (per 1k sec) */
    float rate;
    FILE * srcFiles[2];
    char _gTwoNLinesDelim;
    StrategyCllb cllb;
} config = { 0, 1, {NULL, NULL}, 0, NULL };

void
print_usage(const char * appName, FILE * f) {
    fprintf( f, "Usage:\n\t$ %s [-o <file1>] [-e <file2>] [-f <freq=1>] [-2]\n", appName );
    fprintf( f, "Mimics the real application with its logging system and delays."
            " For given <file1> for stdout, or (and) <file2> for stderr"
            " performs sequential reading of its content, line by line."
            " Once part of the content is read, prints line(s) with mean"
            " frequency specified as -f (1 ev/sec by default) argument"
            " (floating point). If -2 flag is given, the file will be"
            " considered as an array of messages delimited with double"
            " newline characters.\n" );

}

static int
_fromfile_printing() {
    char line[1024], * rd, nStream;
    FILE * srcf = 0
       , * dstf = 0;
    if( !config.srcFiles[0] && !config.srcFiles[1] ) {
        fprintf(stderr, "Error: no input file given!\n");
        return EXIT_FAILURE;
    } else if ( config.srcFiles[0] && config.srcFiles[1] ) {
        nStream = rand()%2;
        srcf = config.srcFiles[(int) nStream];
        dstf = nStream ? stderr : stdout;
    } else {
        srcf = config.srcFiles[0] ? config.srcFiles[0] : config.srcFiles[1];
        dstf = config.srcFiles[0] ? stdout : stderr;
    }
    # ifdef DEBUG
    {
        char bf[128];
        time_t rawtime;
        struct tm * info;
        time(&rawtime);
        info = localtime(&rawtime);
        strftime( bf, 128, "%H:%M:%S", info );
        dbg_print( "%s | ", bf );
    }
    # endif
    if( !feof( srcf ) ){
        if( config._gTwoNLinesDelim ) {
            /* read and print lines from file until next one becomes a newline */
            do {
                rd = fgets(line, sizeof(line), srcf);
                if( rd ) {
                    fputs(line, dstf);
                } else {
                    return 1;
                }
            } while( '\n' != line[0] );
        } else {
            /* read and print single line from file */
            rd = fgets( line, sizeof(line), srcf );
            if( rd ) {
                fputs( line, dstf );
            } else {
                return 1;
            }
        }
        return 0;
    } else {
        return 1;
    }
    return 0;
}

float
delay_to_next( float average ) {
    float u = rand()/((float) RAND_MAX + 1);
    return -log(u)/average;
}

struct {
    size_t nGenerated;
    double timeTaken;
} _procStats;  /* keeps track on process statistics */

/* Performs gracefuls shutdown of the app */
static void
_handle_term(int signal) {
    # ifdef DEBUG
    float avInt;
    if( _procStats.nGenerated ) {
        avInt = _procStats.timeTaken / _procStats.nGenerated;
        dbg_print( "Average messaging interval: %e (%f ev/sec)\n", avInt, 1/avInt );
    }
    _gSigCaught = 1;
    # endif
    fprintf( stderr, "Process exits due to signal \"%d\".\n", signal );
    exit(EXIT_SUCCESS);
}

/* Configures application based on command line arguments */
int
configure_app(int argc, char * argv[]) {
    int c;
    opterr = 0;
    while((c = getopt(argc, argv, "f:o:e:2")) != -1)
        switch (c) {
            case 'f':
                config.rate = atof(optarg);
                break;
            case 'o':
                config.srcFiles[0] = fopen( optarg, "r" );
                break;
            case 'e':
                config.srcFiles[1] = fopen( optarg, "r" );
                break;
            case '2':
                config._gTwoNLinesDelim = 1;
                break;
            default:
                return 1;
        }
    return 0;
}

/* Tests application config for consistency */
int
test_app_config( FILE * estr ) {
    int rc = 0;
    if( _fromfile_printing == config.cllb
     && (!config.srcFiles[0] && !config.srcFiles[1]) ) {
        fputs( "Error: no input file is set, not for stdout, nor"
               " for stderr.\n", estr );
        rc |= 1;
    }
    if( !config.rate ) {
        fputs( "Error: zero event rate.\n", estr );
        rc |= 2;
    }
    return rc;
}

int
main(int argc, char * argv[]) {
    int rc = configure_app(argc, argv);
    float delay;

    /* (shall be set in configure_app()) */
    config.cllb = _fromfile_printing;

    if( rc || (rc = test_app_config(stderr)) ) {
        print_usage( argv[0], stderr );
        return EXIT_FAILURE;
    }

    /* Nullify process statistics */
    memset( &_procStats, 0, sizeof(_procStats));

    /* Set the signal handler for SIGTERM */
    struct sigaction action;
    memset( &action, 0, sizeof(struct sigaction) );
    action.sa_handler = _handle_term;
    sigaction(SIGINT,  &action, NULL);
    sigaction(SIGTERM, &action, NULL);

    for( ; 0 == rc ; ) {
        delay = delay_to_next( config.rate ); /* 1k sec / nEvents per 1k sec */
        dbg_print( "%5f |\n", delay );
        fflush(stdout);
        usleep( delay*1e6 );
        rc = (*config.cllb)();
        _procStats.timeTaken += delay;
        ++ _procStats.nGenerated;
    }
    if( rc > 0 ) {
        return EXIT_SUCCESS;
    } else {
        return EXIT_FAILURE;  /* file exhausted -- ok */
    }
}

