all: mocklog

mocklog: main.c
	g++ -x c $^ -o $@ -Wall -lm -pedantic

clean:
	rm -f mocklog

.PHONY: all clean
