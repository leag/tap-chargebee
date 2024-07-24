from tap_chargebee.streams.base import BaseChargebeeStream
import singer
import time


LOGGER = singer.get_logger()


class PaymentSourcesStream(BaseChargebeeStream):
    TABLE = "payment_sources"
    ENTITY = "payment_source"
    REPLICATION_METHOD = "FULL_TABLE"
    REPLICATION_KEY = "updated_at"
    KEY_PROPERTIES = ["id"]
    BOOKMARK_PROPERTIES = ["updated_at"]
    SELECTED_BY_DEFAULT = True
    VALID_REPLICATION_KEYS = ["updated_at"]
    INCLUSION = "available"
    API_METHOD = "GET"

    def get_url(self):
        return "https://{}.chargebee.com/api/v2/payment_sources".format(
            self.config.get("site")
        )

    def sync_data(self):
        table = self.TABLE
        api_method = self.API_METHOD
        done = False

        LOGGER.info("Starting full table sync for {}.".format(self.TABLE))
        stream_version = int(time.time() * 1000)
        singer.write_version(stream_name=self.TABLE, version=stream_version)
        params = {}
        while not done:
            response = self.client.make_request(
                url=self.get_url(), method=api_method, params=params
            )

            if "api_error_code" in response.keys():
                if response["api_error_code"] == "configuration_incompatible":
                    LOGGER.error("{} is not configured".format(response["error_code"]))
                    break

            records = response.get("list")

            to_write = self.get_stream_data(records)

            with singer.metrics.record_counter(endpoint=table) as ctr:
                for record in to_write:
                    record_message = singer.RecordMessage(
                        stream=table, record=record, version=stream_version
                    )
                    singer.write_message(record_message)
                ctr.increment(amount=len(to_write))

            if not response.get("next_offset"):
                LOGGER.info("Final offset reached. Ending sync.")
                done = True
            else:
                LOGGER.info("Advancing by one offset.")
                params["offset"] = response.get("next_offset")
        singer.write_version(stream_name=self.TABLE, version=stream_version)
        LOGGER.info("Finished syncing {}.".format(self.TABLE))
