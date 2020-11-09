#!/bin/bash
echo "<!DOCTYPE html><html><title>$1</title><xmp theme=\"united\" style=\"display:none;\">"
cat $2
echo "</xmp><script src="https://strapdownjs.com/v/0.2/strapdown.js"></script></html>"
