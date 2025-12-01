"""Network to Provider mapping utility"""

from core.payments.model.paynetwork import Network


class ProviderMapper:
    """Maps network types to provider names"""

    NETWORK_TO_PROVIDER = {
        Network.MTN: "MTN Mobile Money",
        Network.VOD: "Telecel Cash",
        Network.AIR: "AirtelTigo Cash",
    }

    @staticmethod
    def get_provider(network: Network) -> str:
        """
        Get provider name from network enum

        Args:
            network: Network enum value

        Returns:
            Provider name string, or "Unknown" if not found
        """
        return ProviderMapper.NETWORK_TO_PROVIDER.get(network, "Unknown")

    @staticmethod
    def get_provider_from_string(network_str: str) -> str:
        """
        Get provider name from network string

        Args:
            network_str: Network name as string (e.g., "MTN", "VOD", "AIR")

        Returns:
            Provider name string, or "Unknown" if not found
        """
        try:
            network = Network[network_str.upper()]
            return ProviderMapper.get_provider(network)
        except KeyError:
            return "Unknown"
