## Local Development


To run the basic example locally

Navigate to SyftBox Repo

Run

1. Start SyftBox Cache server
```sh
just rs
```

2. Start Client A:

```sh
just rc a
```

3. Start Client B:

```sh
just rc b
```

4. Start Client C:

```sh
just rc c
```


Navigate to Flower Repo

Run

1. Start Aggregator app
```sh
just rs <syftbox_conf_path:<a@openmined.org>>
```

2. Start Client of B
```sh
just rc <syftbox_conf_path:<b@openmined.org>>
```

3. Start Client of C:
```sh
just rc  <syftbox_conf_path:<c@openmined.org>>
```
