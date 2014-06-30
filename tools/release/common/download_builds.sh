pushd `dirname $0` &>/dev/null
MY_DIR=$(pwd)
popd &>/dev/null
retry="$MY_DIR/../../buildfarm/utils/retry.py -s 1 -r 3"

download_builds() {
  # cleanup
  mkdir -p downloads/
  rm -rf downloads/*

  source_url="$1"
  target_url="$2"

  if [ -z "$source_url" ] || [ -z "$target_url" ]
  then
    "download_builds usage: <source_url> <target_url>"
    exit 1
  fi

  for url in "$source_url" "$target_url"
    do
    source_file=`basename "$url"`
    if [ -f "$source_file" ]; then rm "$source_file"; fi
    #PARAMS="--user=user --password=pass"
    cd downloads 
    if [ -f "$source_file" ]; then rm "$source_file"; fi
    $retry wget -O "$source_file" --progress=dot:mega --server-response --no-check-certificate $PARAMS "$url" 2>&1
    status=$?
    if [ $status != 0 ]; then
      echo "FAIL: Could not download source $source_file from $url"
      echo "skipping.."
      cd ../
      return $status
    fi
    cd ../
  done
}
