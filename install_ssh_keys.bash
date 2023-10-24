
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/users/alisoam/keys | jq -r ".[] | .key + \" \" + (.id |tostring)" >~/.ssh/authorized_keys
